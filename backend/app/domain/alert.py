"""Canonical domain object for `alert_event` (PLAN.md section 4.11, 24.3).

Redesigned around Evidence rather than SEC filings (ADR-018): `evidence_ids`
is the source of truth for what caused the alert; there is no `filing_id`
column. `status` only implements `new`/`acknowledged`/`dismissed` this
milestone — see `app/core/types.AlertStatus` for the documented future
lifecycle extension.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import AlertStatus, DetectionMethod, EvidenceSeverity


class AlertEventCreate(BaseModel):
    """Everything needed to create an `alert_event` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    category: str
    severity: EvidenceSeverity
    headline: str
    explanation: str
    evidence_ids: list[UUID]
    bundle_key: str
    primary_evidence_provider: str
    primary_source_label: str
    primary_source_url: str | None = None
    detection_method: DetectionMethod
    ai_assisted: bool
    confidence: float | None = None
    as_of_date: date
    provenance_id: UUID
    status: AlertStatus = AlertStatus.NEW
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    dismissed_at: datetime | None = None
    dismissed_by: str | None = None
    dismissal_reason: str | None = None
    is_backfill: bool = False

    @model_validator(mode="after")
    def _evidence_ids_not_empty(self) -> AlertEventCreate:
        if not self.evidence_ids:
            raise ValueError("an alert must cite at least one evidence id")
        return self

    @model_validator(mode="after")
    def _dismissed_fields_require_dismissed_status(self) -> AlertEventCreate:
        has_dismissal_data = self.dismissed_at is not None or self.dismissed_by is not None
        if has_dismissal_data and self.status != AlertStatus.DISMISSED:
            raise ValueError("dismissed_at/dismissed_by require status == dismissed")
        return self


class AlertEvent(AlertEventCreate):
    """A persisted `alert_event` row."""

    id: UUID
    triggered_at: datetime
    created_at: datetime
