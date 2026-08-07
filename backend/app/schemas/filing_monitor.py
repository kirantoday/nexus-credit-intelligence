"""Response schemas for the Overnight Distress Filing Monitor API (PLAN.md 24.5, 24.8).

Alert wording fields (`headline`/`explanation`) carry through exactly what
`alert_synthesis_service` produced — the API never re-derives or
paraphrases them, so the cautious-wording guarantee holds end to end.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import (
    AlertStatus,
    DetectionMethod,
    EvidenceSeverity,
    EvidenceType,
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    ReviewStatus,
)


class FilingMonitorRunRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: FilingMonitorRunStatus
    mode: FilingMonitorRunMode
    previous_watermark: datetime | None
    resulting_watermark: datetime | None
    issuers_checked: int
    filings_discovered: int
    filings_processed: int
    alerts_created: int
    errors_count: int
    error_summary: str | None
    backfill_lookback_days: int | None
    is_backfill: bool


class FilingMonitorRunsPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    runs: list[FilingMonitorRunRow]


class SecFilingRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    issuer_id: UUID
    issuer_legal_name: str
    accession_no: str
    form_type: str
    filing_date: date
    period_of_report: date | None
    is_amendment: bool
    primary_document_url: str | None


class SecFilingsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    filings: list[SecFilingRow]
    since_run_id: UUID | None


class ResearchEvidenceRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    issuer_id: UUID
    issuer_legal_name: str
    evidence_provider: str
    source_type: str
    filing_id: UUID | None
    docket_entry_id: UUID | None
    evidence_type: EvidenceType
    severity: EvidenceSeverity
    source_section: str | None
    source_item: str | None
    matched_rule: str
    evidence_excerpt: str
    confidence: float | None
    detection_method: DetectionMethod
    review_status: ReviewStatus
    created_at: datetime


class ResearchEvidencePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence: list[ResearchEvidenceRow]


class AlertRow(BaseModel):
    """One evidence-backed alert. `universe_names` is display-only context
    ("which Research Universes is this issuer in") — filtering by universe
    is a separate query parameter, not client-side filtering of this field.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    issuer_id: UUID
    issuer_legal_name: str
    issuer_ticker: str | None
    universe_names: list[str]
    category: str
    severity: EvidenceSeverity
    headline: str
    explanation: str
    evidence_ids: list[UUID]
    detection_method: DetectionMethod
    ai_assisted: bool
    confidence: float | None
    primary_evidence_provider: str
    primary_source_label: str
    primary_source_url: str | None
    as_of_date: date
    triggered_at: datetime
    status: AlertStatus
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    dismissed_at: datetime | None
    dismissed_by: str | None
    dismissal_reason: str | None
    is_backfill: bool


class AlertsPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    alerts: list[AlertRow]
    total: int
    page: int
    page_size: int


class AlertEvidenceDetail(BaseModel):
    """Full evidence detail behind one alert, for the drill-down/expansion
    view (PLAN.md 24.9's "why was it flagged")."""

    model_config = ConfigDict(frozen=True)

    alert: AlertRow
    evidence: list[ResearchEvidenceRow]


class SeverityCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    high: int
    medium: int
    low: int


class MorningBriefSummary(BaseModel):
    """Backs the Morning Research Brief page's summary bar (PLAN.md 24.9,
    Milestone 7.5 section 16 — provider-aware). Deliberately worded to
    outlive SEC being the only evidence provider: no field name here is
    SEC-specific. `new_sec_filings`/`new_court_events`/`new_research_evidence`
    replace the old single "new filings discovered" metric (insufficient
    once CourtListener exists as a second real provider) — each counts by
    `created_at` (when Nexus discovered/persisted the record), never by the
    record's own real-world event date, so a historical backfill discovered
    today correctly shows as new *to Nexus* today without implying the
    underlying event itself happened today (PLAN.md Milestone 7.5 section 17).
    """

    model_config = ConfigDict(frozen=True)

    last_successful_run: FilingMonitorRunRow | None
    latest_run: FilingMonitorRunRow | None
    universes_monitored: int
    issuers_monitored: int
    new_sec_filings: int
    new_court_events: int
    new_research_evidence: int
    actionable_alerts_total: int
    alerts_by_severity: SeverityCounts
    deterministic_alert_count: int
    ai_assisted_alert_count: int
    failures_count: int
    no_new_alerts: bool
