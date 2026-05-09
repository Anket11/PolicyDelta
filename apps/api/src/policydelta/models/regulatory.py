"""Global regulatory corpus (shared across all tenants — no RLS).

Temporal model (docs/ARCHITECTURE.md §3.3): a chunk is in force on date ``d``
iff ``effective_date <= d < expiration_date`` (half-open; NULL = open-ended).
``expiration_date`` is the SOLE retrieval authority. The ``supersessions``
table is lineage metadata for the diff UI and staleness detection — never in
the hot query path. There is deliberately NO stored ``is_active`` boolean.
"""

import datetime as dt
import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, CheckConstraint, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from policydelta.models.base import bigint_pk, created_at_field, tztimestamp_field

EMBEDDING_DIMS = 1536  # text-embedding-3-small


class ExtractionStatus(enum.StrEnum):
    PENDING = "pending"
    REVIEW = "review"  # quarantined: excluded from retrieval until confirmed
    CONFIRMED = "confirmed"


class EffectiveDateSource(enum.StrEnum):
    EXTRACTED = "extracted"
    DEFAULTED_TO_PUBLISHED = "defaulted_to_published"
    OPERATOR_CONFIRMED = "operator_confirmed"


class SupersessionRelation(enum.StrEnum):
    AMENDS = "amends"
    REPEALS = "repeals"
    REPLACES = "replaces"


class RegulatoryDocument(SQLModel, table=True):
    __tablename__ = "regulatory_documents"
    __table_args__ = (
        # Idempotency: same content at one URL = no-op; new content at the same
        # URL = corrected re-publish = NEW row with version+1 (never mutate).
        UniqueConstraint("source_url", "content_hash"),  # uq_…_source_url via convention
        CheckConstraint(
            "extraction_status IN ('pending', 'review', 'confirmed')",
            name="extraction_status_valid",
        ),
    )

    id: int | None = bigint_pk()
    title: str = Field(index=True)
    issuing_body: str = Field(index=True)  # SECP, SBP
    document_type: str = Field(index=True)  # SRO, Circular, Gazette, Notification
    jurisdiction: str = Field(foreign_key="jurisdictions.code", index=True, max_length=16)
    language: str = Field(default="en", max_length=8)
    source_url: str
    source_etag: str | None = None  # latency optimization ONLY, never correctness
    content_hash: str = Field(max_length=64)  # sha256 of extracted markdown
    version: int = Field(default=1)
    published_date: dt.date
    extraction_status: str = Field(default=ExtractionStatus.PENDING.value, max_length=16)
    review_reason: str | None = None  # scanned_pdf | non_english | low_confidence | ...
    raw_markdown: str | None = None  # kept for re-chunk/re-embed; redacted in logs
    ingested_at: dt.datetime | None = created_at_field()


