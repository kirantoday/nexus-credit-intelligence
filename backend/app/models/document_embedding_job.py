"""ORM model for `document_embedding_job` (Milestone 10D.2, ADR-021).

Mirrors `document_extraction`'s job-lifecycle design (claim with `FOR
UPDATE SKIP LOCKED`, bounded attempts, transient/deterministic error
classes, stale-processing reclaim) for embedding one extraction's chunks
under one model.

**Refinement over the Step 0 sketch**: uniqueness is a *partial* unique
index over `(document_extraction_id, embedding_model,
embedding_model_version) WHERE status IN ('pending', 'processing')` — at
most one **active** job per target, not one job ever. A plain unique key
would make it impossible to enqueue a later re-embedding of the same
extraction (after a document title edit, a template version bump, or a
failed attempt) without deleting history. Finished jobs (`completed`,
`failed`, `blocked_ineligible`) are retained as the audit trail.

Counters are cumulative across attempts: each persisted batch increments
them in the same transaction as the embeddings it wrote, so a requeued job
that resumes reports honest totals.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import DocumentExtractionErrorClass, EmbeddingJobStatus
from app.db.base import Base

_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in EmbeddingJobStatus)
_ERROR_CLASS_SQL_LIST = ", ".join(f"'{value}'" for value in DocumentExtractionErrorClass)


class DocumentEmbeddingJob(Base):
    __tablename__ = "document_embedding_job"
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_SQL_LIST})", name="ck_document_embedding_job_status"),
        CheckConstraint(
            f"error_classification IS NULL OR error_classification IN ({_ERROR_CLASS_SQL_LIST})",
            name="ck_document_embedding_job_error_classification",
        ),
        CheckConstraint("dimension > 0", name="ck_document_embedding_job_dimension"),
        CheckConstraint("attempt_count >= 0", name="ck_document_embedding_job_attempt_count"),
        Index("ix_document_embedding_job_status", "status"),
        Index("ix_document_embedding_job_document_extraction_id", "document_extraction_id"),
        Index("ix_document_embedding_job_research_document_id", "research_document_id"),
        Index(
            "ux_document_embedding_job_one_active_per_target",
            "document_extraction_id",
            "embedding_model",
            "embedding_model_version",
            unique=True,
            postgresql_where=text("status IN ('pending', 'processing')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    research_document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_document.id"), nullable=False
    )
    document_extraction_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("document_extraction.id"), nullable=False
    )
    embedding_provider: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Content-free by construction: exception type + classification only
    # (`app.embeddings.errors.safe_summary`), never document text or a raw
    # vendor/driver message.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    chunk_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunks_embedded: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    chunks_replaced: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    provenance_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=True
    )
    requested_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
