"""Assembles the Morning Research Brief (PLAN.md Milestone 7.5.2 correction).

Answers "what materially changed since this user last reviewed the brief?" —
not "how did the last pipeline run go?" (that question still exists, and is
still answered correctly, but only in the secondary `RunDetails` block; see
`_build_run_details`, which is the *unmodified* logic from 7.5.2's original
daily-run-boundary fix, just relocated here since it's Morning Brief domain
logic, not generic filing-monitor API assembly).

No authentication/session infrastructure exists yet (TD-002, open) — `since`
is anchored to a single shared `morning_brief_view` timeline, not a per-user
one. See `app/models/brief_view.py` and TD-018 (PLAN.md) for the documented
interim posture and the real per-user requirement this defers.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
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
    brief_view_repository,
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

# How long since the last recorded view before a *new* one is worth
# recording — keeps rapid refresh/reopen within one working session
# idempotent (the boundary doesn't silently advance mid-session) while
# still advancing naturally for a legitimate later-in-the-day check-in, an
# overnight gap, a weekend, or any longer absence. A heuristic, not a real
# session concept — documented interim behavior pending real per-user
# auth (TD-018).
MIN_VIEW_GAP = timedelta(hours=4)

_BRIEF_TIMEZONE = ZoneInfo("America/New_York")
_FALLBACK_MORNING_HOUR = 6
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _previous_business_day_morning_boundary(now_utc: datetime) -> datetime:
    """First-ever-brief fallback (PLAN.md Milestone 7.5.2 correction): the
    previous Mon-Fri day at 06:00 America/New_York — a documented, sensible
    default, never an arbitrary pipeline-run timestamp. Federal market
    holidays are not specially handled (Mon-Fri only) — low-stakes, since
    this path is only ever reachable once, before any real
    `morning_brief_view` row exists."""
    local_now = now_utc.astimezone(_BRIEF_TIMEZONE)
    candidate = local_now.date() - timedelta(days=1)
    while candidate.weekday() >= 5:  # 5=Saturday, 6=Sunday
        candidate -= timedelta(days=1)
    return datetime.combine(candidate, time(_FALLBACK_MORNING_HOUR, 0), tzinfo=_BRIEF_TIMEZONE)


def _resolve_period_start(db: Session) -> tuple[datetime, bool]:
    """Returns `(period_start, is_fallback)`. `period_start` is the analyst's
    own last recorded brief view when one exists — never a pipeline-run
    watermark — falling back to `_previous_business_day_morning_boundary`
    only for a genuinely first-ever view."""
    latest_view = brief_view_repository.get_latest_view(db)
    if latest_view is not None:
        return latest_view.viewed_at, False
    return _previous_business_day_morning_boundary(datetime.now(UTC)), True


def _should_record_new_view(latest_viewed_at: datetime | None, now: datetime) -> bool:
    """Pure predicate behind `record_brief_view`, factored out for direct
    unit testing (mirrors `enrichment_orchestrator._should_run`'s shape):
    a new view is only worth recording if none exists yet, or the most
    recent one is older than `MIN_VIEW_GAP` — this is what keeps repeated
    calls (a refresh, a background refetch, a double mount) idempotent
    rather than silently advancing the boundary every time."""
    return latest_viewed_at is None or (now - latest_viewed_at) > MIN_VIEW_GAP


def record_brief_view(db: Session) -> None:
    now = datetime.now(UTC)
    latest = brief_view_repository.get_latest_view(db)
    latest_viewed_at = latest.viewed_at if latest is not None else None
    if _should_record_new_view(latest_viewed_at, now):
        brief_view_repository.record_view(db)


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
        errors_count=run.errors_count,
    )


def _latest_successful_daily_run(db: Session) -> DailyRunSummary | None:
    """The one authoritative "latest successful daily run" (PLAN.md
    Milestone 7.5.2 section 4) — whichever of `filing_monitor_run`'s and
    `market_discovery_run`'s latest `delta`/`baseline` success is more
    recent. Unchanged from 7.5.2's original fix — relocated here, not
    rewritten (PLAN.md Milestone 7.5.2 correction: preserve daily-run
    correctness/idempotency/watermark safety exactly as proven live)."""
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


def _build_run_details(db: Session) -> RunDetails:
    """Everything 7.5.2's original fix computed, unchanged: the daily-run
    boundary (mode-scoped, backfill-excluded), and pipeline-run counters
    scoped to *that* boundary — a genuinely different question ("how did
    the last discovery run perform") than the brief's own user-relative
    `period_start` ("what's new to me"). Secondary/diagnostics only."""
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
    new_sec_filings = sec_filing_repository.count_filings_created_since(db, run_since)
    new_court_events = court_docket_entry_repository.count_entries_created_since(db, run_since)
    new_research_evidence = research_evidence_repository.count_evidence_created_since(db, run_since)

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
    across a whole period's worth of developments (PLAN.md Milestone
    7.5.2 correction: a real production request against ~350 alerts timed
    out entirely under the naive per-alert-query version, live-verified
    before this fix)."""
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
    membership changes (if any) for this period, and ranks
    severity-first, most-recent-second — the analyst sees the most
    consequential issuers first. Takes pre-fetched `issuers`/
    `universe_names_by_issuer` maps rather than querying per alert."""
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


# Internal fetch cap for the alert list each period's grouping is built
# from — generous relative to this system's real data volume (hundreds,
# not millions, of alerts per period).
_PERIOD_ALERT_FETCH_LIMIT = 2000

# Display cap on the number of issuer-grouped developments actually
# returned in each of `new_developments`/`historical_intelligence` — a
# real, live-caught necessity, not a stylistic choice: an uncapped
# response against a genuinely large period (e.g. a first-ever brief
# view, which pulls in everything back to the previous business day) was
# measured at 3.5MB, and its JSON-serialization time was long enough to
# occasionally cause the very next request on the same reused connection
# to be rejected by Railway's edge with a spurious 503 — reproduced live,
# not guessed, and not reproducible via any single isolated request.
# `issuers_with_developments`/`historical_intelligence_issuer_count` are
# always the *true* counts, computed before this cap is applied — a
# capped display never misrepresents how much is actually new.
_ISSUER_DISPLAY_CAP = 100


def get_morning_brief(db: Session) -> MorningBriefSummary:
    """ "What materially changed since this user last reviewed the Morning
    Research Brief?" (PLAN.md Milestone 7.5.2 correction) — a pure read, no
    side effects; call `record_brief_view` separately (and only after this
    has already been read) to advance the boundary for next time."""
    period_start, is_fallback = _resolve_period_start(db)
    period_end = datetime.now(UTC)

    alerts, _total = alert_repository.list_alerts(
        db,
        status=AlertStatus.NEW,
        triggered_since=period_start,
        page=1,
        page_size=_PERIOD_ALERT_FETCH_LIMIT,
    )
    new_alerts = [a for a in alerts if not a.is_backfill]
    historical_alerts = [a for a in alerts if a.is_backfill]

    # Batch-fetched once for the whole period's alerts, never per alert or
    # per issuer — the naive per-row version issued two extra queries per
    # alert (an `issuer_repository.get_issuer` + a
    # `collection_repository.list_collections_for_issuer`), which timed out
    # entirely against real production volume (~350 alerts -> 700+ extra
    # round trips) before this was fixed.
    all_issuer_ids = list({a.issuer_id for a in alerts})
    issuers = issuer_repository.list_issuers_by_ids(db, all_issuer_ids)
    universe_collections_by_issuer = collection_repository.list_collections_for_issuers(
        db, all_issuer_ids
    )
    universe_names_by_issuer = {
        issuer_id: [c.name for c in collections]
        for issuer_id, collections in universe_collections_by_issuer.items()
    }

    universe_changes = _universe_changes_by_issuer(db, period_start)

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
        period_start=period_start,
        period_start_is_fallback=is_fallback,
        period_end=period_end,
        issuers_with_developments=len(new_developments),
        severity_counts=severity_counts,
        new_developments=new_developments[:_ISSUER_DISPLAY_CAP],
        historical_intelligence=historical_intelligence[:_ISSUER_DISPLAY_CAP],
        historical_intelligence_issuer_count=len(historical_intelligence),
        no_material_changes=(len(new_developments) == 0),
        run_details=_build_run_details(db),
    )
