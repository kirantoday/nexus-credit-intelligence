"""Canonical domain objects for `document_embedding_job` (Milestone 10D.2).
See `app.models.document_embedding_job` for the lifecycle and the
partial-unique "one active job per target" refinement."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.types import EmbeddingJobStatus


class DocumentEmbeddingJobCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    research_document_id: uuid.UUID
    document_extraction_id: uuid.UUID
    embedding_provider: str
    embedding_model: str
    embedding_model_version: str
    dimension: int
    requested_by: str | None = None


class DocumentEmbeddingJob(BaseModel):
    """A persisted `document_embedding_job` row."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    research_document_id: uuid.UUID
    document_extraction_id: uuid.UUID
    embedding_provider: str
    embedding_model: str
    embedding_model_version: str
    dimension: int
    status: EmbeddingJobStatus
    attempt_count: int
    error_classification: str | None
    error_message: str | None
    status_note: str | None
    chunk_total: int | None
    chunks_embedded: int
    chunks_replaced: int
    provenance_id: uuid.UUID | None
    requested_by: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    # Scheduling (10D.2 scheduling increment). `retry_not_before` is UTC-aware
    # and meaningful only while `pending`; `provider_wide` marks a delay or
    # hold that applies to the whole provider/model queue, not just this job.
    retry_not_before: datetime | None = None
    provider_wide: bool = False
    # Operator-hold evidence. Kept after release: it is history, not state.
    hold_reason: str | None = None
    held_at: datetime | None = None
    released_at: datetime | None = None
    released_by: str | None = None
