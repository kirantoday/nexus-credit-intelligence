"""Issuer Distress Timeline aggregation (PLAN.md Milestone 7.5.4).

Answers "how did this issuer deteriorate over time, and what were the key
events that led from early warning signs to distress/restructuring/
bankruptcy?" using only already-persisted `alert_event` rows — no new
ingestion, no new AI calls, no synthetic events. Every `alert_event` already
represents one deterministic-or-AI-reviewed, non-boilerplate distress signal
(ADR-018's evidence -> bundle -> alert pipeline already did that filtering),
so this module's only real job is:

1. Exclude alerts an analyst dismissed, or that AI review determined were
   about a third party rather than the issuer itself (PLAN.md Milestone
   7.5.1's `issuer_is_subject` fix) — reused here, not re-implemented.
2. Collapse same-day, same-category alerts from different evidence sources
   (e.g. an SEC 8-K and a CourtListener docket entry both about the same
   Chapter 11 filing) into one narrative milestone with multiple source
   badges, instead of rendering near-duplicate cards. Deliberately
   conservative: only an exact (issuer, as_of_date, category) match
   collapses — dates that are merely close never merge, since that would
   risk conflating genuinely distinct events.
3. Order the result by the real-world event date (`as_of_date`), never by
   when Nexus discovered/processed it — the same date-semantics rule PLAN.md
   already applies to the Morning Research Brief.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import AlertStatus, CurationMethod, EvidenceSeverity, VerificationStatus
from app.domain.alert import AlertEvent
from app.repositories import alert_repository, issuer_repository
from app.schemas.issuer_timeline import IssuerTimeline, TimelineEvent, TimelineSource
from app.services import research_universe_service

_SEVERITY_RANK: dict[EvidenceSeverity, int] = {
    EvidenceSeverity.HIGH: 0,
    EvidenceSeverity.MEDIUM: 1,
    EvidenceSeverity.LOW: 2,
}


def _qualifies(alert: AlertEvent) -> bool:
    return alert.status != AlertStatus.DISMISSED and alert.issuer_is_subject is not False


def _primary_sort_key(alert: AlertEvent) -> tuple[int, float, str]:
    """Highest severity first, then highest confidence, then earliest
    triggered — picks the strongest, most-confident alert in a collapsed
    group to supply the timeline entry's headline/explanation/confidence."""
    confidence = alert.confidence if alert.confidence is not None else -1.0
    return (_SEVERITY_RANK[alert.severity], -confidence, alert.triggered_at.isoformat())


def _to_source(alert: AlertEvent) -> TimelineSource:
    return TimelineSource(
        provider=alert.primary_evidence_provider,
        label=alert.primary_source_label,
        url=alert.primary_source_url,
    )


def _group_key(alert: AlertEvent) -> tuple[date, str]:
    return (alert.as_of_date, alert.category)


def _build_event(group: list[AlertEvent]) -> TimelineEvent:
    ordered = sorted(group, key=_primary_sort_key)
    primary = ordered[0]
    supporting = [_to_source(a) for a in ordered[1:]]
    severity = min((a.severity for a in group), key=lambda s: _SEVERITY_RANK[s])
    return TimelineEvent(
        event_date=primary.as_of_date,
        event_type=primary.category,
        title=primary.category.replace("_", " ").title(),
        short_summary=primary.headline,
        why_it_matters=primary.explanation,
        severity=severity,
        confidence=primary.confidence,
        primary_source=_to_source(primary),
        supporting_sources=supporting,
        is_historical_discovery=primary.is_backfill,
        evidence_count=len(group),
    )


def get_issuer_timeline(db: Session, issuer_id: UUID) -> IssuerTimeline | None:
    """`None` when the issuer itself doesn't exist — the route maps that to
    a 404, mirroring `issuer_service.get_issuer_detail`."""
    issuer = issuer_repository.get_issuer(db, issuer_id)
    if issuer is None:
        return None

    alerts = [a for a in alert_repository.list_alerts_by_issuer(db, issuer_id) if _qualifies(a)]

    groups: dict[tuple[date, str], list[AlertEvent]] = defaultdict(list)
    for alert in alerts:
        groups[_group_key(alert)].append(alert)

    events = sorted(
        (_build_event(group) for group in groups.values()),
        key=lambda e: e.event_date,
        reverse=True,
    )

    # Only `verified` memberships are safe to state as current status — a
    # `partial` (system-suggested, unconfirmed) one must never read as a
    # settled fact (PLAN.md Milestone 7.5.1). Manually-curated names are the
    # polished, product-facing labels used everywhere else in the app;
    # System-Detected: * universes exist to classify issuers the curated
    # lists haven't caught up to yet, so they're shown (prefix stripped)
    # only when no curated membership is verified — never both, which would
    # just be the same real status stated twice under different names.
    memberships = research_universe_service.get_issuer_universe_memberships(db, issuer_id)
    verified = [m for m in memberships if m.verification_status == VerificationStatus.VERIFIED]
    curated = {m.name for m in verified if m.curation_method == CurationMethod.MANUAL_CURATED}
    current_status = (
        sorted(curated)
        if curated
        else sorted({m.name.removeprefix("System-Detected: ") for m in verified})
    )

    return IssuerTimeline(
        issuer_id=issuer_id,
        events=events,
        total_events=len(events),
        date_range_start=events[-1].event_date if events else None,
        date_range_end=events[0].event_date if events else None,
        current_status=current_status,
        most_recent_event_title=events[0].title if events else None,
    )
