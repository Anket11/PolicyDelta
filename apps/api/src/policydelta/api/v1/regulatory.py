"""Regulatory corpus browse + semantic search (global, read-only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from policydelta.core.errors import NotFoundError
from policydelta.core.pagination import Page, PageParamsDep
from policydelta.core.tenancy import SCOPE_READ, Principal, SessionDep, require_scope
from policydelta.providers import EmbeddingProvider, get_embedding_provider
from policydelta.retrieval.temporal import resolve_as_of
from policydelta.schemas.regulatory import ChunkOut, DocumentDetail, DocumentSummary
from policydelta.schemas.search import (
    ChunkHit,
    RegulatorySearchRequest,
    RegulatorySearchResponse,
)
from policydelta.services import corpus
from policydelta.services.search import search_regulations

router = APIRouter(prefix="/regulatory", tags=["regulatory"])

ReadPrincipal = Annotated[Principal, Depends(require_scope(SCOPE_READ))]
EmbedderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


@router.get(
    "/documents", operation_id="list_regulatory_documents", response_model=Page[DocumentSummary]
)
async def list_documents(
    _principal: ReadPrincipal,
    session: SessionDep,
    page: PageParamsDep,
    jurisdiction: Annotated[str | None, Query(max_length=16)] = None,
    issuing_body: Annotated[str | None, Query(max_length=64)] = None,
    document_type: Annotated[str | None, Query(max_length=32)] = None,
) -> Page[DocumentSummary]:
    docs, total = await corpus.list_documents(
        session,
        jurisdiction=jurisdiction,
        issuing_body=issuing_body,
        document_type=document_type,
        page=page,
    )
    return Page(
        items=[DocumentSummary.model_validate(doc) for doc in docs],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/documents/{document_id}",
    operation_id="get_regulatory_document",
    response_model=DocumentDetail,
)
async def get_document(
    document_id: int, _principal: ReadPrincipal, session: SessionDep
) -> DocumentDetail:
    found = await corpus.get_document(session, document_id)
    if found is None:
        raise NotFoundError("Regulatory document", document_id)
    doc, chunk_count = found
    return DocumentDetail(
        **DocumentSummary.model_validate(doc).model_dump(),
        source_url=doc.source_url,
        ingested_at=doc.ingested_at,
        chunk_count=chunk_count,
    )


