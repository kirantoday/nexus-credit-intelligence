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


class DailyRunSummary(BaseModel):
    """One "daily run" (PLAN.md Milestone 7.5.2) — deliberately
    pipeline-agnostic: an analyst reading the Morning Research Brief should
    never have to know or care whether `filing_monitor_run` or
    `market_discovery_run` produced it. `pipeline` is kept for operator/
    debugging transparency only, never surfaced as a concept the UI asks
    the analyst to understand. Excludes `mode=backfill` runs entirely — a
    historical backfill is never "the daily run," regardless of how recent
    or how narrow its window (PLAN.md Milestone 7.5.2 section 3/4)."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    pipeline: str
    mode: FilingMonitorRunMode
    status: FilingMonitorRunStatus
    started_at: datetime
    completed_at: datetime | None
    window_start_date: date | None
    window_end_date: date | None
    errors_count: int


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


# NOTE: the Morning Research Brief's response schema (formerly defined here
# as `MorningBriefSummary`) moved to `app.schemas.morning_brief` in
# Milestone 7.5.2's correction — the brief is a user-relative "what changed
# since I last looked" product surface, not a pipeline-run status page, and
# deserves its own module rather than living inside this pipeline-run-
# focused one. `DailyRunSummary`/`SeverityCounts` above are still reused
# there (imported, not duplicated) for the secondary `run_details` block.
