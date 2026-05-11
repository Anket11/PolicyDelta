"""Candidate retrieval: temporally-filtered ANN + exact-citation merge.

Soft threshold policy (docs/ARCHITECTURE.md §4.1): drop obvious junk above the
distance ceiling, but ALWAYS keep the best surviving candidate flagged
``weak_match`` — a hard threshold silently hides law; we'd rather show a weak
match than fabricate a clean "no result".
"""

import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from policydelta.models import RegulatoryChunk, RegulatoryDocument
from policydelta.retrieval.citations import extract_citations
from policydelta.retrieval.temporal import as_of_predicate, in_force_chunks

#: Over-retrieve from the ANN, trim after thresholding.
ANN_CANDIDATES = 24
#: Cosine-distance ceiling (similarity ≥ 0.45). Eval-tuned knob, not a truth.
DISTANCE_CEILING = 0.55

CandidateSource = Literal["vector", "citation"]


@dataclass(frozen=True)
class Candidate:
    chunk: RegulatoryChunk
    distance: float | None  # None for pure citation hits
    weak_match: bool
    source: CandidateSource


def _embedding_column() -> Any:
    return cast("Any", RegulatoryChunk.__table__.c.embedding)  # type: ignore[attr-defined]


async def vector_search(
    session: AsyncSession,
    query_vector: list[float],
    *,
    jurisdiction: str,
    as_of: dt.date,
    top_k: int,
) -> list[Candidate]:
    distance_expr = _embedding_column().cosine_distance(query_vector)
    stmt = (
        select(RegulatoryChunk, distance_expr.label("distance"))
        .join(
            RegulatoryDocument,
            col(RegulatoryChunk.document_id) == col(RegulatoryDocument.id),
        )
        .where(as_of_predicate(jurisdiction, as_of))
        .order_by(distance_expr)
        .limit(ANN_CANDIDATES)
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return []

    candidates = [
        Candidate(chunk=chunk, distance=float(distance), weak_match=False, source="vector")
        for chunk, distance in rows
    ]
    within = [c for c in candidates if c.distance is not None and c.distance <= DISTANCE_CEILING]
    if within:
        return within[:top_k]
    # Nothing under the ceiling: surface the single best hit, honestly flagged.
    best = candidates[0]
    return [Candidate(chunk=best.chunk, distance=best.distance, weak_match=True, source="vector")]


