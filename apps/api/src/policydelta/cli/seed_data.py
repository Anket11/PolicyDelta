"""Development/test seed corpus (docs/ARCHITECTURE.md §8.3).

Six documents engineered to exercise every temporal edge the truth-table
tests assert on. Idempotent: re-running is a no-op (keyed on source_url).
Embeddings come from the deterministic FakeEmbeddings — seeding never costs
OpenAI money; `policydelta seed --real-embeddings` is a later upgrade.
"""

import datetime as dt
import hashlib
from dataclasses import dataclass, field

from policydelta.models import (
    EffectiveDateSource,
    ExtractionStatus,
    SupersessionRelation,
)

SEED_JURISDICTION = ("PK", "Pakistan")
SEED_ORGS = (("PocketPay", "PK"), ("Acme Corp", "PK"))


@dataclass(frozen=True)
class SeedChunk:
    legal_citation: str
    heading_path: str
    content: str
    effective_date: dt.date
    expiration_date: dt.date | None = None
    effective_date_source: str = EffectiveDateSource.EXTRACTED.value


@dataclass(frozen=True)
class SeedDocument:
    key: str  # stable handle used by tests/supersession wiring
    title: str
    issuing_body: str
    document_type: str
    source_url: str
    published_date: dt.date
    chunks: list[SeedChunk] = field(default_factory=list)
    extraction_status: str = ExtractionStatus.CONFIRMED.value
    review_reason: str | None = None


@dataclass(frozen=True)
class SeedSupersession:
    superseded_doc_key: str
    superseding_doc_key: str
    relation: str
    effective_date: dt.date


def embed_text_for(chunk: SeedChunk) -> str:
    """Breadcrumb-prefixed text — what actually gets embedded (recall win)."""
    return f"[{chunk.heading_path}] {chunk.content}"


def content_hash_for(doc: SeedDocument) -> str:
    joined = "\n\n".join(chunk.content for chunk in doc.chunks)
    return hashlib.sha256(joined.encode()).hexdigest()


