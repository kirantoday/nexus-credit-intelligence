"""Request/response schemas for Document Intelligence (Milestone 10C).

Kept as its own layer, independent of `app.domain.document_extraction`/
`app.domain.document_chunk` — routes depend on schemas, not domain objects
directly (PLAN.md section 3), matching `app.schemas.research_document`'s
established shape exactly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import AccessClassification, DocumentChunkElementType, DocumentExtractionStatus
from app.domain.document_chunk import DocumentChunk
from app.domain.document_extraction import DocumentExtraction


class DocumentExtractionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    research_document_id: UUID | None
    status: DocumentExtractionStatus
    extractor_provider: str | None
    extractor_version: str | None
    chunking_strategy_version: str | None
    page_count: int | None
    chunk_count: int | None
    table_count: int | None
    attempt_count: int
    error_classification: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    is_current: bool

    @staticmethod
    def from_domain(extraction: DocumentExtraction) -> DocumentExtractionResponse:
        return DocumentExtractionResponse(
            id=extraction.id,
            research_document_id=extraction.research_document_id,
            status=extraction.status,
            extractor_provider=extraction.extractor_provider,
            extractor_version=extraction.extractor_version,
            chunking_strategy_version=extraction.chunking_strategy_version,
            page_count=extraction.page_count,
            chunk_count=extraction.chunk_count,
            table_count=extraction.table_count,
            attempt_count=extraction.attempt_count,
            error_classification=extraction.error_classification,
            error_message=extraction.error_message,
            started_at=extraction.started_at,
            completed_at=extraction.completed_at,
            created_at=extraction.created_at,
            is_current=extraction.is_current,
        )


class DocumentExtractionListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    extractions: list[DocumentExtractionResponse]


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    document_extraction_id: UUID
    research_document_id: UUID
    issuer_id: UUID
    chunk_index: int
    element_type: DocumentChunkElementType
    content: str
    content_type: str
    page_start: int | None
    page_end: int | None
    section_path: str | None
    section_title: str | None
    token_count: int | None
    confidentiality_classification: AccessClassification
    created_at: datetime

    @staticmethod
    def from_domain(chunk: DocumentChunk) -> DocumentChunkResponse:
        return DocumentChunkResponse(
            id=chunk.id,
            document_extraction_id=chunk.document_extraction_id,
            research_document_id=chunk.research_document_id,
            issuer_id=chunk.issuer_id,
            chunk_index=chunk.chunk_index,
            element_type=chunk.element_type,
            content=chunk.content,
            content_type=chunk.content_type,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_path=chunk.section_path,
            section_title=chunk.section_title,
            token_count=chunk.token_count,
            confidentiality_classification=chunk.confidentiality_classification,
            created_at=chunk.created_at,
        )


class DocumentChunkListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunks: list[DocumentChunkResponse]
