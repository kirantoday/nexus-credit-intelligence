"""ORM model for `embedding_call_log` (Milestone 10D.2, ADR-021) — one row
per real embedding-provider request.

A dedicated ledger rather than new values in `ai_call_log`, because that
table's `operation`/`route` CHECKs, NOT NULL `routing_reason`, run-FK
shape, haiku/sonnet-specific aggregation, and output-token-dependent cost
estimate all describe chat completions, and embeddings would misrepresent
or break each (evidence in ADR-021). It deliberately mirrors `ai_call_log`'s
spirit: tokens, estimated cost, latency, success, retries, error class.

`input_tokens` and `estimated_cost_usd` are nullable and **null means
unknown, never zero** (same rule as `app.ai.pricing`). `job_id` is nullable
so future evaluation and query-embedding calls, which belong to no job, can
use the same ledger.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import EmbeddingInputType
from app.db.base import Base

_PURPOSE_SQL_LIST = ", ".join(f"'{value}'" for value in EmbeddingInputType)


class EmbeddingCallLog(Base):
    __tablename__ = "embedding_call_log"
    __table_args__ = (
        CheckConstraint(f"purpose IN ({_PURPOSE_SQL_LIST})", name="ck_embedding_call_log_purpose"),
        CheckConstraint("batch_size > 0", name="ck_embedding_call_log_batch_size"),
        Index("ix_embedding_call_log_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("document_embedding_job.id"), nullable=True
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
