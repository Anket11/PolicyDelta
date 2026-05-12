"""The job worker: claim → per-job tenant context → execute → settle.

Design (docs/ARCHITECTURE.md §3.6): the queue is GLOBAL (no RLS) precisely so
the worker can see jobs across tenants; tenant isolation re-engages the moment
work starts — each job runs in a fresh transaction with SET LOCAL tenant
context, so RLS governs every tenant-scoped read/write the job performs.
Claiming uses FOR UPDATE SKIP LOCKED (safe for N workers); the lease + reaper
recover jobs orphaned by a crashed/redeployed instance.
"""

import asyncio
import contextlib
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from policydelta.audit.service import execute_audit_run
from policydelta.ingestion.fetch import fetch_document
from policydelta.ingestion.service import IngestHints, ingest_bytes, ingest_markdown
from policydelta.models import JobKind, RunStatus
from policydelta.providers.base import ChatProvider, EmbeddingProvider

logger = structlog.get_logger(__name__)

LEASE_TIMEOUT = dt.timedelta(minutes=15)

_CLAIM_SQL = text(
    """
    UPDATE jobs
    SET status = 'running', locked_at = now(), locked_by = :worker, attempts = attempts + 1
    WHERE id = (
        SELECT id FROM jobs
        WHERE status = 'queued'
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, kind, ref_id, tenant_id, attempts, max_attempts, payload
    """
)

_SETTLE_SQL = text(
    "UPDATE jobs SET status = :status, error = :error, locked_at = NULL, locked_by = NULL "
    "WHERE id = :job_id"
)

_REQUEUE_SQL = text(
    "UPDATE jobs SET status = 'queued', locked_at = NULL, locked_by = NULL, error = :error "
    "WHERE id = :job_id"
)

_REAP_SQL = text(
    """
    UPDATE jobs
    SET status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
        error = COALESCE(error, 'lease expired'),
        locked_at = NULL, locked_by = NULL
    WHERE status = 'running'
      AND locked_at < now() - make_interval(secs => :lease_seconds)
    RETURNING id
    """
)


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    kind: str
    ref_id: int | None
    tenant_id: int | None
    attempts: int
    max_attempts: int
    payload: dict[str, Any]


