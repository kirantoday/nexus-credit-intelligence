"""Canonical domain objects for `embedding_call_log` (Milestone 10D.2). One
row per real provider request; `None` token/cost values mean unknown, never
zero. See `app.models.embedding_call_log`."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.types import EmbeddingInputType


class EmbeddingCallLogCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: uuid.UUID | None = None
    purpose: EmbeddingInputType
    provider: str
    model: str
    model_version: str | None = None
    batch_size: int
    input_tokens: int | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    success: bool
    retry_count: int = 0
    error_classification: str | None = None


class EmbeddingCallLog(EmbeddingCallLogCreate):
    """A persisted `embedding_call_log` row."""

    id: uuid.UUID
    created_at: datetime


class EmbeddingJobUsageSummary(BaseModel):
    """Aggregated spend for one job, computed at read time from the ledger
    (never stored redundantly on the job). `total_estimated_cost_usd` is
    `None` when *any* contributing call had an unknown cost — a partial sum
    would silently understate spend."""

    model_config = ConfigDict(frozen=True)

    total_calls: int
    failed_calls: int
    total_input_tokens: int
    calls_with_unknown_tokens: int
    total_estimated_cost_usd: float | None
