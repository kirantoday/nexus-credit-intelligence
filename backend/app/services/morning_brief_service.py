"""Assembles the Morning Research Brief (PLAN.md Milestone 7.5.2,
business-day-cycle correction).

Answers "what materially changed during the latest completed business-day
research cycle, compared with the preceding one?" — not "how did the last
pipeline run go?" (still answered, but only in the secondary `RunDetails`
block) and, since a prior correction attempt, deliberately **not** "since
this browser last viewed the page." A page view is not a research
boundary: opening, refreshing, or revisiting the brief must never change
what counts as "new" — only a new successful daily/delta run completing
does. `latest_research_day`/`preceding_research_day` are pure functions of
canonical run data plus calendar business-day arithmetic; nothing in this
module reads or writes any view/visit state.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.types import AlertStatus, CollectionType, EvidenceSeverity
from app.domain.alert import AlertEvent
from app.domain.filing_monitor_run import FilingMonitorRun
from app.domain.issuer import Issuer
from app.domain.market_discovery import MarketDiscoveryRun
from app.repositories import (
    alert_repository,
    collection_repository,
    court_docket_entry_repository,
    filing_monitor_run_repository,
    issuer_repository,
    market_discovery_repository,
    research_evidence_repository,
    sec_filing_repository,
)
from app.schemas.filing_monitor import AlertRow, DailyRunSummary, SeverityCounts
from app.schemas.morning_brief import (
    IssuerDevelopment,
    MorningBriefSummary,
    RunDetails,
    UniverseMembershipChange,
)

_BRIEF_TIMEZONE = ZoneInfo("America/New_York")
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _to_et_date(dt: datetime) -> date:
    return dt.astimezone(_BRIEF_TIMEZONE).date()


def _previous_business_day(d: date) -> date:
    """The business day strictly before `d` — Mon-Fri only, weekends
    skipped. Pure calendar arithmetic: never requires a second real run to
    exist, so even the very first daily run ever completed has a
    well-defined comparison boundary (PLAN.md Milestone 7.5.2's
    business-day-cycle correction)."""
    candidate = d - timedelta(days=1)
    while candidate.weekday() >= 5:  # 5=Saturday, 6=Sunday
        candidate -= timedelta(days=1)
    return candidate


def _most_recent_business_day(d: date) -> date:
    """`d` itself if it's a business day, else the most recent business day
    on or before it (walking back from a Saturday lands on Friday)."""
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _filing_monitor_research_day(run: FilingMonitorRun) -> date:
    """`filing_monitor_run` has no window fields — `previous_watermark` is
    the start of what it covered (mirrors `market_discovery_run.
    window_start_date`), falling back to `started_at` only when no prior
    watermark exists (a first-ever baseline run)."""
    if run.previous_watermark is not None:
        return _to_et_date(run.previous_watermark)
    return _to_et_date(run.started_at)


def _filing_monitor_run_to_daily_summary(run: FilingMonitorRun) -> DailyRunSummary:
    return DailyRunSummary(
        id=run.id,
        pipeline="filing_monitor",
        mode=run.mode,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        window_start_date=None,
        window_end_date=None,
        research_day=_filing_monitor_research_day(run),
        errors_count=run.errors_count,
    )


def _market_discovery_run_to_daily_summary(run: MarketDiscoveryRun) -> DailyRunSummary:
    return DailyRunSummary(
        id=run.id,
        pipeline="market_discovery",
        mode=run.mode,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        window_start_date=run.window_start_date,
        window_end_date=run.window_end_date,
        research_day=run.window_start_date,
        errors_count=run.errors_count,
    )


def _latest_successful_daily_run(db: Session) -> DailyRunSummary | None:
    """The one authoritative "latest successful daily run" (PLAN.md
    Milestone 7.5.2 section 4) — whichever of `filing_monitor_run`'s and
    `market_discovery_run`'s latest `delta`/`baseline` success is more
    recent by `completed_at`. Unchanged from 7.5.2's original fix."""
    candidates: list[tuple[datetime, DailyRunSummary]] = []
    fm_run = filing_monitor_run_repository.get_latest_successful_daily_run(db)
    if fm_run is not None and fm_run.completed_at is not None:
        candidates.append((fm_run.completed_at, _filing_monitor_run_to_daily_summary(fm_run)))
    md_run = market_discovery_repository.get_latest_successful_daily_run(db)
    if md_run is not None and md_run.completed_at is not None:
        candidates.append((md_run.completed_at, _market_discovery_run_to_daily_summary(md_run)))
    if not candidates:
        return None
    return max(candidates, key=lambda c: c[0])[1]


def _latest_daily_run(db: Session) -> DailyRunSummary | None:
    """The most recent `delta`/`baseline` run of either pipeline regardless
    of outcome — backs `RunDetails`'s "current run" status."""
    candidates: list[tuple[datetime, DailyRunSummary]] = []
    fm_run = filing_monitor_run_repository.get_latest_daily_run(db)
    if fm_run is not None:
        candidates.append((fm_run.started_at, _filing_monitor_run_to_daily_summary(fm_run)))
    md_run = market_discovery_repository.get_latest_daily_run(db)
    if md_run is not None:
        candidates.append((md_run.started_at, _market_discovery_run_to_daily_summary(md_run)))
    if not candidates:
        return None
    return max(candidates, key=lambda c: c[0])[1]


def resolve_research_cycle(db: Session) -> tuple[date, date, bool]:
    """Returns `(latest_research_day, preceding_research_day, is_fallback)`.
    `latest_research_day` is the `research_day` of the latest successful
    daily run when one exists; `preceding_research_day` is always the
    business day immediately before it, by calendar arithmetic — never a
    second real run lookup, so a single completed daily run already has a
    well-defined comparison. `is_fallback=True` only when no successful
    daily run has *ever* completed, in which case both days fall back to
    the most recent business day on/before today (America/New_York) and
    the one before it — a documented default, never an arbitrary
    timestamp, and reachable only once per fresh deployment."""
    latest = _latest_successful_daily_run(db)
    if latest is not None:
        latest_research_day = latest.research_day
        is_fallback = False
    else:
        today_et = _to_et_date(datetime.now(UTC))
        latest_research_day = _most_recent_business_day(today_et)
        is_fallback = True
    preceding_research_day = _previous_business_day(latest_research_day)
    return latest_research_day, preceding_research_day, is_fallback


def _build_run_details(
    db: Session, *, preceding_research_day: date, latest_research_day: date
) -> RunDetails:
    """Pipeline-run identity/status fields (`last_successful_run`/
    `latest_run`/`since`) are unchanged from 7.5.2's original fix —
    "how did the last discovery run perform," a genuinely different
    question from the brief's own `latest_research_day`. Secondary/
    diagnostics only.

    `new_sec_filings`/`new_court_events`/`new_research_evidence`, however,
    are scoped to the *research cycle's* `(preceding_research_day,
    latest_research_day]` window by each record's own real-world source
    date — not `since` (a specific run's `started_at`) — per the same
    2026-08-10 correction as the alert partitioning below: a one-time
    explicit `--mode backfill` window used to correct a watermark gap
    still belongs to the research cycle whose event dates it actually
    covers, regardless of which run/mode ingested it."""
    latest_successful = _latest_successful_daily_run(db)
    latest_run = _latest_daily_run(db)
    run_since = latest_successful.started_at if latest_successful else None

    universes_monitored = len(
        collection_repository.list_collections(db, collection_type=CollectionType.RESEARCH_UNIVERSE)
    ) + len(collection_repository.list_collections(db, collection_type=CollectionType.BENCHMARK))
    issuers_monitored = len(
        collection_repository.list_issuer_ids_for_collection_types(
            db, [CollectionType.RESEARCH_UNIVERSE, CollectionType.BENCHMARK]
        )
    )
    new_sec_filings = sec_filing_repository.count_filings_by_filing_date_between(
        db, preceding_research_day, latest_research_day
    )
    new_court_events = court_docket_entry_repository.count_entries_by_entry_date_between(
        db, preceding_research_day, latest_research_day
    )
    new_research_evidence = research_evidence_repository.count_evidence_by_source_date_between(
        db, preceding_research_day, latest_research_day
    )

    return RunDetails(
        last_successful_run=latest_successful,
        latest_run=latest_run,
        since=run_since,
        universes_monitored=universes_monitored,
        issuers_monitored=issuers_monitored,
        new_sec_filings=new_sec_filings,
        new_court_events=new_court_events,
        new_research_evidence=new_research_evidence,
        failures_count=(latest_run.errors_count if latest_run else 0),
    )


def _universe_changes_by_issuer(
    db: Session, since: datetime
) -> dict[str, list[UniverseMembershipChange]]:
    changed = collection_repository.list_system_seeded_memberships_changed_since(db, since)
    result: dict[str, list[UniverseMembershipChange]] = defaultdict(list)
    for membership, collection in changed:
        change_type: Literal["added", "upgraded"] = (
            "added" if membership.added_at >= since else "upgraded"
        )
        result[str(membership.issuer_id)].append(
            UniverseMembershipChange(
                universe_name=collection.name,
                change_type=change_type,
                verification_status=membership.verification_status,
            )
        )
    return result


def _alert_to_row(alert: AlertEvent, issuer: Issuer | None, universe_names: list[str]) -> AlertRow:
    """Builds an `AlertRow` from already-fetched issuer/universe data —
    unlike `filing_monitor_api_service.alert_to_row`, this issues no
    queries of its own, so it stays cheap when called once per alert
    across a whole cycle's worth of developments (PLAN.md Milestone 7.5.2
    correction: a real production request against ~350 alerts timed out
    entirely under the naive per-alert-query version, live-verified before
    this fix)."""
    return AlertRow(
        id=alert.id,
        issuer_id=alert.issuer_id,
        issuer_legal_name=issuer.legal_name if issuer else "Unknown issuer",
        issuer_ticker=issuer.ticker if issuer else None,
        universe_names=universe_names,
        category=alert.category,
        severity=alert.severity,
        headline=alert.headline,
        explanation=alert.explanation,
        evidence_ids=alert.evidence_ids,
        detection_method=alert.detection_method,
        ai_assisted=alert.ai_assisted,
        confidence=alert.confidence,
        primary_evidence_provider=alert.primary_evidence_provider,
        primary_source_label=alert.primary_source_label,
        primary_source_url=alert.primary_source_url,
        as_of_date=alert.as_of_date,
        triggered_at=alert.triggered_at,
        status=alert.status,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        dismissed_at=alert.dismissed_at,
        dismissed_by=alert.dismissed_by,
        dismissal_reason=alert.dismissal_reason,
        is_backfill=alert.is_backfill,
    )


def _group_by_issuer(
    alerts: list[AlertEvent],
    universe_changes: dict[str, list[UniverseMembershipChange]],
    issuers: dict[UUID, Issuer],
    universe_names_by_issuer: dict[UUID, list[str]],
) -> list[IssuerDevelopment]:
    """Groups alerts by issuer (the brief's fundamental display unit, not
    an individual alert), attaches that issuer's Research Universe
    membership changes (if any) for this cycle, and ranks severity-first,
    most-recent-second — the analyst sees the most consequential issuers
    first. Takes pre-fetched `issuers`/`universe_names_by_issuer` maps
    rather than querying per alert."""
    by_issuer: dict[str, list[AlertEvent]] = defaultdict(list)
    for alert in alerts:
        by_issuer[str(alert.issuer_id)].append(alert)

    developments: list[IssuerDevelopment] = []
    for issuer_id_str, issuer_alerts in by_issuer.items():
        issuer_id = issuer_alerts[0].issuer_id
        issuer = issuers.get(issuer_id)
        sorted_alerts = sorted(
            issuer_alerts,
            key=lambda a: (_SEVERITY_RANK[a.severity.value], -a.triggered_at.timestamp()),
        )
        max_severity = min(
            (a.severity for a in issuer_alerts), key=lambda s: _SEVERITY_RANK[s.value]
        )
        universe_names = universe_names_by_issuer.get(issuer_id, [])
        developments.append(
            IssuerDevelopment(
                issuer_id=issuer_id,
                issuer_legal_name=issuer.legal_name if issuer else "Unknown issuer",
                issuer_ticker=issuer.ticker if issuer else None,
                max_severity=max_severity,
                alerts=[_alert_to_row(a, issuer, universe_names) for a in sorted_alerts],
                universe_changes=universe_changes.get(issuer_id_str, []),
            )
        )

    developments.sort(
        key=lambda d: (
            _SEVERITY_RANK[d.max_severity.value],
            -max(a.triggered_at for a in d.alerts).timestamp(),
        )
    )
    return developments


# Internal fetch cap for the alert list each cycle's grouping is built
# from — generous relative to this system's real data volume (hundreds,
# not millions, of alerts per cycle).
_PERIOD_ALERT_FETCH_LIMIT = 2000

# Display cap on the number of issuer-grouped developments actually
# returned in each of `new_developments`/`historical_intelligence` — a
# real, live-caught necessity: an uncapped response against a genuinely
# large window was measured at 3.5MB. `issuers_with_developments`/
# `historical_intelligence_issuer_count` are always the *true* counts,
# computed before this cap is applied.
_ISSUER_DISPLAY_CAP = 100


def is_new_development(
    alert: AlertEvent, *, preceding_research_day: date, latest_research_day: date
) -> bool:
    """The 2026-08-10 correction: whether an alert belongs in
    `new_developments` vs. `historical_intelligence` is decided by its
    real-world `as_of_date` relative to the research-cycle boundary
    `(preceding_research_day, latest_research_day]` — never by
    `is_backfill`. `is_backfill` describes *how the row was ingested*
    (which pipeline mode created it); it is not, and was never meant to
    be, a proxy for *when the underlying event actually happened*. That
    distinction was invisible as long as every explicit-window ingestion
    genuinely was old data — it broke the day a one-time explicit
    `--mode backfill --start/--end` window was used to correct a
    watermark gap and ingest genuinely current (Aug 9-10) activity,
    which `is_backfill=True` then mislabeled as historical. `is_backfill`
    itself is untouched and still exposed on `AlertRow` as ingestion
    provenance — this function only changes which bucket an alert is
    displayed in, nothing about the row's own persisted data."""
    return preceding_research_day < alert.as_of_date <= latest_research_day


def get_morning_brief(db: Session) -> MorningBriefSummary:
    """ "What materially changed during the latest completed business-day
    research cycle, compared with the preceding one?" (PLAN.md Milestone
    7.5.2's business-day-cycle correction) — a pure function of canonical
    run data and calendar arithmetic, no side effects, and no dependency
    on any view/visit state. Calling this any number of times in a row
    returns identical `latest_research_day`/`preceding_research_day`
    values until a new successful daily/delta run actually completes."""
    latest_research_day, preceding_research_day, is_fallback = resolve_research_cycle(db)
    since = datetime.combine(latest_research_day, time(0, 0), tzinfo=_BRIEF_TIMEZONE)
    as_of = datetime.now(UTC)

    alerts, _total = alert_repository.list_alerts(
        db,
        status=AlertStatus.NEW,
        triggered_since=since,
        page=1,
        page_size=_PERIOD_ALERT_FETCH_LIMIT,
    )
    new_alerts = []
    historical_alerts = []
    for a in alerts:
        if is_new_development(
            a,
            preceding_research_day=preceding_research_day,
            latest_research_day=latest_research_day,
        ):
            new_alerts.append(a)
        else:
            historical_alerts.append(a)

    # Batch-fetched once for the whole cycle's alerts, never per alert or
    # per issuer — the naive per-row version issued two extra queries per
    # alert, which timed out entirely against real production volume
    # before this was fixed.
    all_issuer_ids = list({a.issuer_id for a in alerts})
    issuers = issuer_repository.list_issuers_by_ids(db, all_issuer_ids)
    universe_collections_by_issuer = collection_repository.list_collections_for_issuers(
        db, all_issuer_ids
    )
    universe_names_by_issuer = {
        issuer_id: [c.name for c in collections]
        for issuer_id, collections in universe_collections_by_issuer.items()
    }

    universe_changes = _universe_changes_by_issuer(db, since)

    new_developments = _group_by_issuer(
        new_alerts, universe_changes, issuers, universe_names_by_issuer
    )
    historical_intelligence = _group_by_issuer(
        historical_alerts, universe_changes, issuers, universe_names_by_issuer
    )

    severity_counts = SeverityCounts(
        high=sum(1 for a in new_alerts if a.severity == EvidenceSeverity.HIGH),
        medium=sum(1 for a in new_alerts if a.severity == EvidenceSeverity.MEDIUM),
        low=sum(1 for a in new_alerts if a.severity == EvidenceSeverity.LOW),
    )

    return MorningBriefSummary(
        latest_research_day=latest_research_day,
        preceding_research_day=preceding_research_day,
        research_cycle_is_fallback=is_fallback,
        as_of=as_of,
        issuers_with_developments=len(new_developments),
        severity_counts=severity_counts,
        new_developments=new_developments[:_ISSUER_DISPLAY_CAP],
        historical_intelligence=historical_intelligence[:_ISSUER_DISPLAY_CAP],
        historical_intelligence_issuer_count=len(historical_intelligence),
        no_material_changes=(len(new_developments) == 0),
        run_details=_build_run_details(
            db,
            preceding_research_day=preceding_research_day,
            latest_research_day=latest_research_day,
        ),
    )
