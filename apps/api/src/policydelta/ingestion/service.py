"""Ingestion orchestrator: bytes/markdown → quarantine checks → chunks → embeddings.

Commits in stages (document+chunks, then per embedding batch) so a crash
mid-embedding loses nothing: ``backfill_embeddings`` resumes exactly where
``embedded_at IS NULL``. Corrected re-publishes (same URL, new content) create
a NEW version row; prior versions are quarantined to review — past audit
findings stay resolvable, the corrected text takes over retrieval.
"""

import datetime as dt
import hashlib
from dataclasses import dataclass

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from policydelta.ingestion.chunker import chunk_document
from policydelta.ingestion.extract import (
    extract_markdown,
    has_injection_patterns,
    is_non_english_primary,
    is_scanned,
)
from policydelta.ingestion.metadata import extract_metadata
from policydelta.models import (
    ExtractionStatus,
    RegulatoryChunk,
    RegulatoryDocument,
)
from policydelta.providers.base import EmbeddingProvider

logger = structlog.get_logger(__name__)

EMBED_PERSIST_BATCH = 64


@dataclass(frozen=True)
class IngestHints:
    source_url: str
    title: str
    issuing_body: str
    document_type: str
    jurisdiction: str
    published_date: dt.date
    source_etag: str | None = None


@dataclass(frozen=True)
class IngestOutcome:
    document_id: int
    status: str
    review_reason: str | None
    chunk_count: int
    deduped: bool
    supersedes_refs: list[str]


def _hash(data: bytes | str) -> str:
    raw = data.encode() if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


async def _existing_by_hash(
    session: AsyncSession, source_url: str, content_hash: str
) -> int | None:
    return (
        await session.execute(
            select(col(RegulatoryDocument.id)).where(
                col(RegulatoryDocument.source_url) == source_url,
                col(RegulatoryDocument.content_hash) == content_hash,
            )
        )
    ).scalar_one_or_none()


