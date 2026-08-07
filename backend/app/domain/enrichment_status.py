"""Canonical domain object for `issuer_enrichment_status` (PLAN.md Milestone 7.5 section 8).

See the ORM model's docstring for why this table exists and how
`app/services/enrichment_orchestrator.py` uses it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import EnrichmentStatus, ProviderName


class IssuerEnrichmentStatusCreate(BaseModel):
    """Everything needed to create an `issuer_enrichment_status` row."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    provider: ProviderName
    status: EnrichmentStatus = EnrichmentStatus.PENDING
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    next_retry_at: datetime | None = None
    attempt_count: int = 0
    records_found: int = 0
    error_classification: str | None = None
    checkpoint: dict | None = None


class IssuerEnrichmentStatus(IssuerEnrichmentStatusCreate):
    """A persisted `issuer_enrichment_status` row."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class IssuerEnrichmentStatusUpdate(BaseModel):
    """A narrow update applied after one enrichment attempt completes.

    Mirrors `filing_monitor_run_repository.complete_run`'s pattern: "record
    the outcome of an attempt" is a narrow, single-purpose write, not a
    general-purpose upsert of arbitrary fields.
    """

    model_config = ConfigDict(frozen=True)

    status: EnrichmentStatus
    last_attempt_at: datetime
    last_success_at: datetime | None = None
    next_retry_at: datetime | None = None
    records_found: int | None = None
    error_classification: str | None = None
    checkpoint: dict | None = None
