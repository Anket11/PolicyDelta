"""The audit pipeline: split → embed → retrieve → judge → ground → roll up.

Retrieval runs sequentially (one AsyncSession is not concurrency-safe); LLM
judging fans out under a semaphore (no session involvement). A clause whose
LLM call fails is an ``error`` outcome — never silently compliant.
"""

import asyncio
import datetime as dt
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from policydelta.audit.grounding import quote_is_grounded
from policydelta.audit.prompt import SYSTEM_PROMPT, build_user_payload
from policydelta.audit.schema import ClauseVerdict, Verdict
from policydelta.models import RegulatoryDocument, RunStatus, RunVerdict
from policydelta.providers.base import ChatProvider, EmbeddingProvider, TokenUsage
from policydelta.retrieval.candidates import (
    Candidate,
    citation_lookup,
    merge_candidates,
    vector_search,
)
from policydelta.retrieval.policy_split import PolicyClause, split_policy

logger = structlog.get_logger(__name__)

CLAUSE_CONCURRENCY = 5
TOP_K_PER_CLAUSE = 8
LOW_CONFIDENCE_THRESHOLD = 0.6


@dataclass(frozen=True)
class ResolvedFinding:
    clause_index: int
    offending_policy_text: str
    legal_rule_text: str
    citation: str
    source_chunk_id: int | None
    source_document_id: int | None
    source_url: str
    risk_level: str
    grounding_quote: str
    rationale: str
    suggested_fix: str
    confidence: float
    needs_review: bool


@dataclass
class ClauseOutcome:
    clause: PolicyClause
    verdict: Verdict | None  # None == LLM call errored
    findings: list[ResolvedFinding] = field(default_factory=list)
    error: str | None = None
    dropped_ungrounded: int = 0
    retrieved_chunk_ids: list[int] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(frozen=True)
class PipelineResult:
    clauses: list[PolicyClause]
    outcomes: list[ClauseOutcome]
    status: RunStatus
    verdict: RunVerdict | None
    coverage: dict[str, int]
    total_prompt_tokens: int
    total_completion_tokens: int
    retrieved_chunk_ids: list[int]


