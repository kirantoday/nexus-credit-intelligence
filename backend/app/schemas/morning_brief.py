"""Response schemas for the Morning Research Brief (PLAN.md Milestone 7.5.2
correction, business-day-cycle revision: "What materially changed during
the latest completed business-day research cycle compared with the
preceding one?" — not a pipeline-run status page, and not a per-user
"since you last looked" page view either).

`MorningBriefSummary` is deliberately structured so the primary fields an
analyst reads (`new_developments`, `historical_intelligence`,
`severity_counts`) never share a namespace with operational pipeline
counters — those live in `run_details`, a secondary/diagnostics block.
"""

from __future__ import annotations

from datetime import date, datetime
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
    pipeline run's own `started_at` boundary — the same underlying run data
    `latest_research_day` is itself derived from, just exposed here in its
    original operational-diagnostics form (raw run counters) rather than
    the brief's primary business-day framing."""

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
    """The Morning Research Brief. `latest_research_day`/`preceding_research_day`
    define the comparison window — "what materially changed during the
    latest completed business-day research cycle compared with the
    preceding one" (PLAN.md Milestone 7.5.2's business-day-cycle
    correction). Both are derived purely from canonical successful
    daily-run data and calendar business-day arithmetic — never from a
    page view, a request timestamp, or `datetime.now()` at read time.
    Opening, refreshing, or revisiting the brief can never change these
    values; only a *new* successful daily/delta run completing can.

    `latest_research_day` is the `research_day` (see `DailyRunSummary`) of
    the most recent successful `delta`/`baseline` run of either pipeline.
    `preceding_research_day` is the business day immediately before it
    (Mon-Fri only, weekends skipped) — computed by calendar arithmetic, not
    by requiring a second real run to exist, so the very first daily run
    ever completed already has a well-defined comparison boundary.
    `research_cycle_is_fallback=True` only when no successful daily run has
    ever completed at all, in which case both days fall back to the most
    recent business day on/before today and the one before it.

    `new_developments`/`historical_intelligence` are both issuer-grouped and
    severity-ranked, and are a strict partition of alerts triggered on or
    after the start of `latest_research_day` (America/New_York) by
    `alert_event.is_backfill`: `new_developments` are alerts the discovery
    run's own narrow window created (`is_backfill=False` — genuinely new
    events), `historical_intelligence` are alerts the enrichment
    orchestrator's wider lookback surfaced (`is_backfill=True` — an old
    event Nexus just happened to discover this cycle). The same issuer can
    appear in both, since the split is per-alert, not per-issuer.
    `severity_counts` covers `new_developments` only.
    """

    model_config = ConfigDict(frozen=True)

    latest_research_day: date
    preceding_research_day: date
    research_cycle_is_fallback: bool
    as_of: datetime
    issuers_with_developments: int
    severity_counts: SeverityCounts
    new_developments: list[IssuerDevelopment]
    historical_intelligence: list[IssuerDevelopment]
    historical_intelligence_issuer_count: int
    no_material_changes: bool
    run_details: RunDetails
