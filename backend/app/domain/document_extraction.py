"""Canonical domain objects for `document_extraction` (Milestone 10C).

See `app.models.document_extraction`'s module docstring for the
immutable-attempt/`is_current`-promotion design. Repository functions that
transition state (`claim_pending_extraction`, `complete_extraction`, ...)
take explicit keyword arguments rather than a generic `*Update` object —
mirrors `market_discovery_repository.complete_run`'s established shape,
not `research_document_repository.apply_metadata_update`'s, since each
transition has a genuinely different, non-overlapping set of fields it
sets.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.types import DocumentExtractionSourceType, DocumentExtractionStatus


class DocumentExtractionCreate(BaseModel):
    """Everything needed to enqueue a new (pending) extraction attempt."""

    model_config = ConfigDict(frozen=True)

    source_type: DocumentExtractionSourceType
    research_document_id: uuid.UUID


class DocumentExtraction(BaseModel):
    """A persisted `document_extraction` row."""

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    source_type: DocumentExtractionSourceType
    research_document_id: uuid.UUID | None
    status: DocumentExtractionStatus

    extractor_provider: str | None
    extractor_version: str | None
    chunking_strategy_version: str | None

    structured_artifact_storage_key: str | None

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
