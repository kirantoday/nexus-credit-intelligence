"""Repository for `document_chunk` (Milestone 10C).

Function-style, domain objects only, flush-not-commit. `search_chunks`
backs the internal `search_document_chunks` debug/inspection capability —
plain Postgres full-text search (`search_vector @@ plainto_tsquery`),
the same primitive Milestone 12A already uses everywhere else, scoped to
one extraction at a time. Deliberately no vector/semantic search (10C
scope).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import AccessClassification, DocumentChunkElementType
from app.domain.document_chunk import DocumentChunk, DocumentChunkCreate
from app.models.document_chunk import DocumentChunk as DocumentChunkModel


def _to_domain(row: DocumentChunkModel) -> DocumentChunk:
    return DocumentChunk(
        id=row.id,
        document_extraction_id=row.document_extraction_id,
        research_document_id=row.research_document_id,
        issuer_id=row.issuer_id,
        chunk_index=row.chunk_index,
        element_type=DocumentChunkElementType(row.element_type),
        content=row.content,
        content_type=row.content_type,
        page_start=row.page_start,
        page_end=row.page_end,
        section_path=row.section_path,
        section_title=row.section_title,
        token_count=row.token_count,
        confidentiality_classification=AccessClassification(row.confidentiality_classification),
        created_at=row.created_at,
    )


def create_chunks(db: Session, chunks: list[DocumentChunkCreate]) -> list[DocumentChunk]:
    """Bulk-inserts every chunk for one extraction in a single flush —
    never one `INSERT` per chunk. Ordering follows `chunk_index`, matching
    insertion order the caller already produced deterministically."""
    rows = [
        DocumentChunkModel(
            document_extraction_id=chunk.document_extraction_id,
            research_document_id=chunk.research_document_id,
            issuer_id=chunk.issuer_id,
            chunk_index=chunk.chunk_index,
            element_type=chunk.element_type.value,
            content=chunk.content,
            content_type=chunk.content_type,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_path=chunk.section_path,
            section_title=chunk.section_title,
            token_count=chunk.token_count,
            confidentiality_classification=chunk.confidentiality_classification.value,
        )
        for chunk in chunks
    ]
    db.add_all(rows)
    db.flush()
    for row in rows:
        db.refresh(row)
    return [_to_domain(row) for row in rows]


def list_for_extraction(db: Session, document_extraction_id: uuid.UUID) -> list[DocumentChunk]:
    stmt = (
        select(DocumentChunkModel)
        .where(DocumentChunkModel.document_extraction_id == document_extraction_id)
        .order_by(DocumentChunkModel.chunk_index)
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def get_chunk(db: Session, chunk_id: uuid.UUID) -> DocumentChunk | None:
    row = db.get(DocumentChunkModel, chunk_id)
    return _to_domain(row) if row is not None else None


def count_for_extraction(db: Session, document_extraction_id: uuid.UUID) -> int:
    stmt = select(func.count()).where(
        DocumentChunkModel.document_extraction_id == document_extraction_id
    )
    return db.execute(stmt).scalar_one()


def search_chunks(
    db: Session, document_extraction_id: uuid.UUID, *, query: str, limit: int = 50
) -> list[DocumentChunk]:
    """Internal lexical inspection search — `search_document_chunks`
    (Milestone 10C section 14), never registered with Universal Search.
    Plain `plainto_tsquery`, the same primitive `search_repository`
    already uses for every other entity's fallback tier."""
    stmt = (
        select(DocumentChunkModel)
        .where(
            DocumentChunkModel.document_extraction_id == document_extraction_id,
            DocumentChunkModel.search_vector.op("@@")(func.plainto_tsquery("english", query)),
        )
        .order_by(DocumentChunkModel.chunk_index)
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
