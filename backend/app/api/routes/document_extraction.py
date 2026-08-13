"""Document Intelligence API routes (Milestone 10C).

Thin per PLAN.md section 3: delegates to `document_extraction_service`/
repositories, no business logic here. Two routers, matching the URL
shapes the milestone brief specifies: extraction lifecycle nests under
the existing `/api/research-documents/{id}` resource; chunk access nests
under `/api/document-extractions/{id}` (a chunk belongs to an extraction,
not directly to a document — matches the canonical model). Neither route
performs extraction inline — `POST .../process` only ever creates a
`pending` row and returns; the worker
(`app.scripts.run_document_extraction_worker`) does the actual work.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import document_chunk_repository, document_extraction_repository
from app.schemas.document_extraction import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentExtractionListResponse,
    DocumentExtractionResponse,
)
from app.services import document_extraction_service
from app.services.document_extraction_service import (
    ResearchDocumentArchivedForProcessingError,
    ResearchDocumentNotFoundError,
)

research_document_extractions_router = APIRouter(
    prefix="/api/research-documents", tags=["document-intelligence"]
)
document_extraction_router = APIRouter(
    prefix="/api/document-extractions", tags=["document-intelligence"]
)


@research_document_extractions_router.post(
    "/{document_id}/process",
    response_model=DocumentExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
def process_document(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    requested_by: Annotated[str | None, Body(embed=True)] = None,
) -> DocumentExtractionResponse:
    try:
        extraction = document_extraction_service.enqueue_extraction(
            db, document_id, requested_by=requested_by
        )
    except ResearchDocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ResearchDocumentArchivedForProcessingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DocumentExtractionResponse.from_domain(extraction)


@research_document_extractions_router.get(
    "/{document_id}/extractions", response_model=DocumentExtractionListResponse
)
def list_extractions(
    document_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> DocumentExtractionListResponse:
    extractions = document_extraction_repository.list_for_document(db, document_id)
    return DocumentExtractionListResponse(
        extractions=[DocumentExtractionResponse.from_domain(e) for e in extractions]
    )


@research_document_extractions_router.get(
    "/{document_id}/extractions/current", response_model=DocumentExtractionResponse
)
def get_current_extraction(
    document_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> DocumentExtractionResponse:
    extraction = document_extraction_repository.get_current_for_document(db, document_id)
    if extraction is None:
        raise HTTPException(status_code=404, detail="No current extraction for this document")
    return DocumentExtractionResponse.from_domain(extraction)


@document_extraction_router.get("/{extraction_id}", response_model=DocumentExtractionResponse)
def get_extraction(
    extraction_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> DocumentExtractionResponse:
    extraction = document_extraction_repository.get_extraction(db, extraction_id)
    if extraction is None:
        raise HTTPException(status_code=404, detail="document_extraction not found")
    return DocumentExtractionResponse.from_domain(extraction)


@document_extraction_router.get("/{extraction_id}/chunks", response_model=DocumentChunkListResponse)
def list_chunks(
    extraction_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> DocumentChunkListResponse:
    if document_extraction_repository.get_extraction(db, extraction_id) is None:
        raise HTTPException(status_code=404, detail="document_extraction not found")
    chunks = document_chunk_repository.list_for_extraction(db, extraction_id)
    return DocumentChunkListResponse(chunks=[DocumentChunkResponse.from_domain(c) for c in chunks])


@document_extraction_router.get(
    "/{extraction_id}/chunks/search", response_model=DocumentChunkListResponse
)
def search_chunks(
    extraction_id: UUID, q: str, db: Annotated[Session, Depends(get_db)]
) -> DocumentChunkListResponse:
    """Internal lexical inspection search (`search_document_chunks`,
    milestone brief section 14) — scoped to one extraction, never exposed
    through Universal Search."""
    if document_extraction_repository.get_extraction(db, extraction_id) is None:
        raise HTTPException(status_code=404, detail="document_extraction not found")
    if not q.strip():
        return DocumentChunkListResponse(chunks=[])
    chunks = document_chunk_repository.search_chunks(db, extraction_id, query=q.strip())
    return DocumentChunkListResponse(chunks=[DocumentChunkResponse.from_domain(c) for c in chunks])
