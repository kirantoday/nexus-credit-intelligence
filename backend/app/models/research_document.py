"""ORM model for `research_document` (PLAN.md 4.10; Milestone 10B).

Distinct from `docket_document` (court filings retrieved/uploaded against a
specific docket entry) — this is general analyst research material (credit
agreements, presentations, internal memos) associated directly with an
issuer. Mirrors `research_note`'s "no hard delete, ever" posture: archiving
is the only removal path (`is_archived`/`archived_at`/`archived_by`), same
shape as `app.models.research.ResearchNote`.

`confidentiality_classification` reuses `AccessClassification`'s
`standard`/`restricted` values (the same two-value set `research_note.
access_classification` already uses) rather than a new, parallel enum with
identical values — captured and displayed, not enforced by any route
dependency, for the same reason `research_note.access_classification` isn't
(TD-025): no real identity/roles exist yet (`AUTH_ENABLED=false`).

`extracted_text` is a reserved, nullable slot per PLAN.md 4.10's own sketch —
Milestone 10B never populates it (no PDF extraction in this milestone). A
future document-intelligence milestone may populate it directly for simple
whole-document search, or supersede it with a richer
`document_extraction`/`document_chunk` model for page-aware RAG citations —
that decision is explicitly deferred, not made here.

The physical file (bytes, checksum, content type, size, Supabase Storage
path) lives on `raw_provider_payload` via `raw_payload_id`, not duplicated
here — this table is identity/workflow metadata only, per the "distinguish
document identity from physical file storage" architecture review.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import AccessClassification, ResearchDocumentType
from app.db.base import Base

_DOCUMENT_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in ResearchDocumentType)
_CONFIDENTIALITY_SQL_LIST = ", ".join(f"'{value}'" for value in AccessClassification)

# search_vector (Milestone 10B-5, extending Universal Search/Milestone 12A)
# — title only, plus document_type/description as lower-weighted metadata.
# Deliberately never references `extracted_text`: no PDF extraction exists
# in this codebase, so this column must never imply document-content search.
# Plain `||`, not `concat_ws` — see app.models.research's identical note.
_RESEARCH_DOCUMENT_SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', "
    "replace(coalesce(document_type, ''), '_', ' ')), 'C') || "
    "setweight(to_tsvector('english', coalesce(description, '')), 'C')"
)


class ResearchDocument(Base):
    __tablename__ = "research_document"
    __table_args__ = (
        CheckConstraint(
            f"document_type IN ({_DOCUMENT_TYPE_SQL_LIST})",
            name="ck_research_document_document_type",
        ),
        CheckConstraint(
            f"confidentiality_classification IN ({_CONFIDENTIALITY_SQL_LIST})",
            name="ck_research_document_confidentiality_classification",
        ),
        CheckConstraint(
            "(is_archived AND archived_at IS NOT NULL) "
            "OR (NOT is_archived AND archived_at IS NULL)",
            name="ck_research_document_archived_requires_timestamp",
        ),
        Index("ix_research_document_issuer_id", "issuer_id"),
        Index("ix_research_document_security_id", "security_id"),
        Index("ix_research_document_is_archived", "is_archived"),
        Index("ix_research_document_raw_payload_id", "raw_payload_id"),
        Index("ix_research_document_provenance_id", "provenance_id"),
        Index("ix_research_document_search_vector", "search_vector", postgresql_using="gin"),
    )

    # No `server_default=gen_random_uuid()` fallback here (unlike this
    # project's other models): `research_document_service` always generates
    # `id` client-side *before* the Storage upload, so the same id can be
    # embedded in the Storage object key — the id must exist before this row
    # does. Always pass `id` explicitly on insert.
    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    security_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("security.id"), nullable=True
    )
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("raw_provider_payload.id"), nullable=False
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidentiality_classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'standard'")
    )
    uploaded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed(_RESEARCH_DOCUMENT_SEARCH_VECTOR_SQL, persisted=True), nullable=True
    )
