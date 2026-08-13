"""ORM model for `document_chunk` (Milestone 10C) — the canonical
retrieval unit produced from one `document_extraction` attempt.

`research_document_id`/`issuer_id`/`confidentiality_classification` are
deliberate denormalizations off `document_extraction`/`research_document`,
copied at chunk-creation time — the same "convenience field, not the
authoritative source" precedent `alert_event.primary_source_label`/
`primary_source_url` already established (ADR-018). Two independent
reasons: (1) filtering chunks by issuer/document never needs a join
through `document_extraction`, and (2) `confidentiality_classification`
being *always present directly on the row a future retrieval query reads*
is a guardrail property, not just a performance one — it makes "did this
query check access classification" an explicit, visible predicate instead
of something a future author could forget five joins deep.

`search_vector` (generated, GIN-indexed) mirrors the exact pattern
Milestone 12A established (`research_document.search_vector`,
`court_docket.search_vector`, ...) — reused here for the internal
`search_document_chunks` capability (10C), never registered with
Universal Search's `search_service._GROUP_FUNCTIONS`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import AccessClassification, DocumentChunkElementType
from app.db.base import Base

_ELEMENT_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in DocumentChunkElementType)
_CONFIDENTIALITY_SQL_LIST = ", ".join(f"'{value}'" for value in AccessClassification)

_DOCUMENT_CHUNK_SEARCH_VECTOR_SQL = "to_tsvector('english', coalesce(content, ''))"


class DocumentChunk(Base):
    __tablename__ = "document_chunk"
    __table_args__ = (
        CheckConstraint(
            f"element_type IN ({_ELEMENT_TYPE_SQL_LIST})", name="ck_document_chunk_element_type"
        ),
        CheckConstraint(
            f"confidentiality_classification IN ({_CONFIDENTIALITY_SQL_LIST})",
            name="ck_document_chunk_confidentiality_classification",
        ),
        CheckConstraint(
            "page_start IS NULL OR page_end IS NULL OR page_start <= page_end",
            name="ck_document_chunk_page_range_valid",
        ),
        UniqueConstraint(
            "document_extraction_id", "chunk_index", name="ux_document_chunk_extraction_ordinal"
        ),
        Index("ix_document_chunk_document_extraction_id", "document_extraction_id"),
        Index("ix_document_chunk_research_document_id", "research_document_id"),
        Index("ix_document_chunk_issuer_id", "issuer_id"),
        Index("ix_document_chunk_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_extraction_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("document_extraction.id"), nullable=False
    )
    research_document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_document.id"), nullable=False
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    element_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'markdown'")
    )

    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Deterministic approximation (len(content) // 4), never a real
    # tokenizer count — documented at the point of computation
    # (`app.extraction.chunker`), not implied to be exact.
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    confidentiality_classification: Mapped[str] = mapped_column(Text, nullable=False)

    # `clock_timestamp()`, not `now()` — same reasoning as
    # `document_extraction.created_at` (see that model's comment); a bulk
    # `create_chunks` insert for one extraction is a single statement, but
    # a future caller re-chunking or a test creating chunks across
    # multiple calls in one transaction should not tie either.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_DOCUMENT_CHUNK_SEARCH_VECTOR_SQL, persisted=True), nullable=True
    )
