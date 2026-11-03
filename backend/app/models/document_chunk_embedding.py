"""ORM model for `document_chunk_embedding` (Milestone 10D.2, ADR-021) — a
dedicated, FK-linked embedding table, replacing PLAN.md 4.9's polymorphic
`embedding(source_table, source_id)` sketch (see ADR-021 and ADR-018's
per-source-FK precedent).

**Uniqueness and replacement semantics.** `(chunk_id, embedding_model,
embedding_model_version)` is unique: at most one vector per chunk per
model version. The same key being embedded again with a *different*
`content_fingerprint` (document title edited, input template bumped)
replaces the row in place in a single upsert statement, incrementing
`revision` — never delete-then-insert, so a valid vector is never removed
before its replacement exists. A different model *version* is a different
key, so old and new vectors coexist until an explicit, separately approved
retirement. `document_chunk` rows themselves are immutable (the repository
has no update/delete path), so chunk *content* cannot change under a
stored vector; staleness arises from the title/section/template/model
inputs captured in `content_fingerprint`.

**Width.** `embedding` is a fixed-width `vector(N)`; N is
`app.embeddings.dimensions.EMBEDDING_COLUMN_DIMENSION` — a draft pilot
value pending provider approval. It cannot be changed in place; a different
width needs a new column/table and re-embedding. `CHECK (vector_dims(
embedding) = dimension)` keeps each row's recorded dimension honest.

No ANN index in 10D.2: exact cosine scans first (ADR-021).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.vector_type import Vector
from app.embeddings.dimensions import EMBEDDING_COLUMN_DIMENSION

_SHA256_RE = "^[0-9a-f]{64}$"


class DocumentChunkEmbedding(Base):
    __tablename__ = "document_chunk_embedding"
    __table_args__ = (
        CheckConstraint(
            f"content_fingerprint ~ '{_SHA256_RE}'",
            name="ck_document_chunk_embedding_fingerprint_format",
        ),
        CheckConstraint(
            "vector_dims(embedding) = dimension", name="ck_document_chunk_embedding_dim"
        ),
        CheckConstraint("revision >= 1", name="ck_document_chunk_embedding_revision"),
        Index(
            "ux_document_chunk_embedding_chunk_model",
            "chunk_id",
            "embedding_model",
            "embedding_model_version",
            unique=True,
        ),
        Index("ix_document_chunk_embedding_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("document_chunk.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("document_embedding_job.id"), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_COLUMN_DIMENSION), nullable=False)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
