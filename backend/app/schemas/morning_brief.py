"""Response schemas for the Morning Research Brief (PLAN.md Milestone 7.5.2
correction: "What materially changed since this user last reviewed the
Morning Research Brief?" — not a pipeline-run status page).

`MorningBriefSummary` is deliberately structured so the primary fields an
analyst reads (`new_developments`, `historical_intelligence`,
`severity_counts`) never share a namespace with operational pipeline
counters — those live in `run_details`, a secondary/diagnostics block.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import EvidenceSeverity, VerificationStatus
from app.schemas.filing_monitor import AlertRow, DailyRunSummary, SeverityCounts


class UniverseMembershipChange(BaseModel):
    """One Research Universe membership change for an issuer, surfaced only
    because it is itself a material research development — "an issuer's
    membership changed," not routine universe bookkeeping (PLAN.md
    Milestone 7.5.2 correction). `change_type="added"` is a brand-new
    membership (`collection_membership.added_at` fell in this period);
    `"upgraded"` is an existing membership's `verification_status`
    strengthening (`.updated_at` fell in this period, e.g. `partial` ->
    `verified`). Membership *removal* is not represented — the live daily
    path never removes a membership; only the separate, manual Milestone
    7.5.1 reconciliation script does."""

    model_config = ConfigDict(frozen=True)

    universe_name: str
    change_type: Literal["added", "upgraded"]
    verification_status: VerificationStatus


class IssuerDevelopment(BaseModel):
    """One issuer's material developments this period — the brief's
    fundamental unit of display, not an individual alert. `alerts` is
    ranked severity-first, most-recent-second; `max_severity` is what
    the summary counts and the section-level sort key are computed from."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    issuer_legal_name: str
    issuer_ticker: str | None
    max_severity: EvidenceSeverity
    alerts: list[AlertRow]
    universe_changes: list[UniverseMembershipChange]


class RunDetails(BaseModel):
    """Secondary, diagnostics-only pipeline-run detail (PLAN.md Milestone
    7.5.2 correction) — everything the original 7.5.2 daily-run-boundary
    fix computed (`last_successful_run`/`latest_run` mode-scoped selection,
    watermark safety, provider-agnostic run counters) is preserved here
    unchanged, just moved out of the analyst's primary view. `since` is the
    pipeline run's own boundary (PLAN.md Milestone 7.5.2 section 4) — a
    genuinely different question ("how did the last discovery run perform")
    than the brief's user-relative `period_start` ("what's new to me")."""

    model_config = ConfigDict(frozen=True)

    last_successful_run: DailyRunSummary | None
    latest_run: DailyRunSummary | None
    since: datetime | None
    universes_monitored: int
    issuers_monitored: int
    new_sec_filings: int
    new_court_events: int
    new_research_evidence: int
    failures_count: int


class MorningBriefSummary(BaseModel):
    """The Morning Research Brief. `period_start` is user-relative — the
    boundary of the analyst's own last brief view (`morning_brief_view`),
    never a pipeline-run watermark — with `period_start_is_fallback=True`
    only for a genuinely first-ever view (no prior `morning_brief_view` row
    exists), in which case `period_start` is the previous business-day
    morning boundary, not an arbitrary run timestamp.

    `new_developments`/`historical_intelligence` are both issuer-grouped and
    severity-ranked, and are a strict partition of this period's actionable
    alerts by `alert_event.is_backfill`: `new_developments` are alerts the
    discovery run's own narrow window created (`is_backfill=False` —
    genuinely new events), `historical_intelligence` are alerts the
    enrichment orchestrator's wider lookback surfaced (`is_backfill=True` —
    an old event Nexus just happened to discover this period). The same
    issuer can appear in both, since the split is per-alert, not per-issuer.
    `severity_counts` covers `new_developments` only — historical
    intelligence is deliberately not counted into the primary summary
    numbers, matching its de-emphasized presentation.
    """

    model_config = ConfigDict(frozen=True)

    period_start: datetime
    period_start_is_fallback: bool
    period_end: datetime
    issuers_with_developments: int
    severity_counts: SeverityCounts
    new_developments: list[IssuerDevelopment]
    historical_intelligence: list[IssuerDevelopment]
    historical_intelligence_issuer_count: int
    no_material_changes: bool
    run_details: RunDetails
