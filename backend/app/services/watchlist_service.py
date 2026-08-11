"""Assembles the Watchlists API (PLAN.md section 24.1; Milestone 8).

Watchlists answer "which issuers do I personally care about, and what's
changed?" — a personal/organizational tracking list, distinct from the
curated Research Universes that share the same `collection`/
`collection_membership` tables (ADR-016), discriminated by
`collection_type=watchlist`. This module creates zero new intelligence: it
only organizes and aggregates alerts, memberships, and securities that
already exist, reusing the exact same research-cycle semantics as the
Morning Research Brief (`morning_brief_service.resolve_research_cycle` /
`is_new_development`) so "new development" means one single thing across
the whole product. Building a Watchlist view makes zero Anthropic calls.

Per PLAN.md's no-per-user-auth posture (TD-002), every Watchlist is
`scope=personal`/`owner_user_id=None` — a single shared analyst workspace,
not per-user data. This module does not invent user accounts.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import (
    AlertStatus,
    CollectionScope,
    CollectionType,
    CurationMethod,
    EvidenceSeverity,
    VerificationStatus,
)
from app.domain.alert import AlertEvent
from app.domain.collection import Collection, CollectionCreate, CollectionMembershipCreate
from app.repositories import (
    alert_repository,
    collection_repository,
    issuer_repository,
    security_repository,
)
from app.schemas.research_universe import IssuerUniverseMembership
from app.schemas.watchlist import (
    WatchlistDetailResponse,
    WatchlistIssuerRow,
    WatchlistSummary,
)
from app.services import issuer_timeline_service, morning_brief_service, research_universe_service

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "watchlist"
    return base


def _unique_slug(db: Session, name: str) -> str:
    """Watchlist names need not be unique (an analyst may reasonably create
    two similarly-named lists), but `collection.slug` is a DB-unique
    identifier — collisions are resolved silently with a numeric suffix
    rather than rejecting the create."""
    base = _slugify(name)
    slug = base
    suffix = 2
    while collection_repository.get_collection_by_slug(db, slug) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _issuer_row(
    *,
    issuer_id: UUID,
    issuer_legal_name: str,
    issuer_ticker: str | None,
    rationale: str,
    added_at: datetime,
    alerts_by_issuer: dict[UUID, list[AlertEvent]],
    memberships_by_issuer: dict[UUID, list[IssuerUniverseMembership]],
    securities_count_by_issuer: dict[UUID, int],
    preceding_research_day: date,
    latest_research_day: date,
) -> WatchlistIssuerRow:
    qualifying = [
        a for a in alerts_by_issuer.get(issuer_id, []) if issuer_timeline_service.qualifies(a)
    ]
    latest = (
        max(qualifying, key=lambda a: (a.as_of_date, -_SEVERITY_RANK[a.severity.value]))
        if qualifying
        else None
    )
    new_count = sum(
        1
        for a in qualifying
        if morning_brief_service.is_new_development(
            a,
            preceding_research_day=preceding_research_day,
            latest_research_day=latest_research_day,
        )
    )
    current_status = research_universe_service.derive_current_status(
        memberships_by_issuer.get(issuer_id, [])
    )
    return WatchlistIssuerRow(
        issuer_id=issuer_id,
        issuer_legal_name=issuer_legal_name,
        issuer_ticker=issuer_ticker,
        current_status=current_status,
        latest_development_headline=latest.headline if latest else None,
        latest_development_date=latest.as_of_date if latest else None,
        severity=latest.severity if latest else None,
        new_developments_count=new_count,
        securities_count=securities_count_by_issuer.get(issuer_id, 0),
        rationale=rationale,
        added_at=added_at,
    )


def _build_rows(db: Session, collection_id: UUID) -> list[WatchlistIssuerRow]:
    members = collection_repository.list_issuers_for_collection(db, collection_id)
    issuer_ids = [issuer.id for issuer, _membership in members]
    if not issuer_ids:
        return []

    alerts_by_issuer = alert_repository.list_alerts_by_issuers(db, issuer_ids)
    memberships_by_issuer = research_universe_service.get_issuer_universe_memberships_batch(
        db, issuer_ids
    )
    securities_count_by_issuer = security_repository.count_securities_by_issuers(db, issuer_ids)
    latest_research_day, preceding_research_day, _is_fallback = (
        morning_brief_service.resolve_research_cycle(db)
    )

    rows = [
        _issuer_row(
            issuer_id=issuer.id,
            issuer_legal_name=issuer.legal_name,
            issuer_ticker=issuer.ticker,
            rationale=membership.rationale,
            added_at=membership.added_at,
            alerts_by_issuer=alerts_by_issuer,
            memberships_by_issuer=memberships_by_issuer,
            securities_count_by_issuer=securities_count_by_issuer,
            preceding_research_day=preceding_research_day,
            latest_research_day=latest_research_day,
        )
        for issuer, membership in members
    ]
    rows.sort(
        key=lambda r: (
            _SEVERITY_RANK.get(r.severity.value if r.severity else "low", 2),
            -(r.latest_development_date.toordinal() if r.latest_development_date else 0),
            r.issuer_legal_name,
        )
    )
    return rows


def _alert_status_counts(db: Session, issuer_ids: list[UUID]) -> tuple[int, int]:
    """Alert *workflow-status* counts for a Watchlist's issuers (Milestone
    9) — `alert.status=new`, deliberately distinct from this module's own
    "new development" (research-cycle) counts above. A Watchlist can
    correctly show "0 new developments this cycle" while still having
    unacknowledged alerts from an earlier cycle, and vice versa; conflating
    the two would silently redefine "new" for one of the two products
    (PLAN.md 24.11)."""
    if not issuer_ids:
        return 0, 0
    new_alert_count = alert_repository.count_alerts(
        db, status=AlertStatus.NEW, issuer_ids=issuer_ids
    )
    high_severity_alert_count = alert_repository.count_alerts(
        db, status=AlertStatus.NEW, severity=EvidenceSeverity.HIGH, issuer_ids=issuer_ids
    )
    return new_alert_count, high_severity_alert_count


def _to_summary(
    db: Session,
    collection: Collection,
    rows: list[WatchlistIssuerRow],
    *,
    contains_issuer: bool | None = None,
) -> WatchlistSummary:
    issuers_with_new = sum(1 for r in rows if r.new_developments_count > 0)
    high_severity_count = sum(
        1
        for r in rows
        if r.severity is not None and r.severity.value == "high" and r.new_developments_count > 0
    )
    activity_candidates: list[datetime] = [r.added_at for r in rows]
    last_activity_at = max(activity_candidates) if activity_candidates else None
    new_alert_count, high_severity_alert_count = _alert_status_counts(
        db, [r.issuer_id for r in rows]
    )
    return WatchlistSummary(
        id=collection.id,
        slug=collection.slug,
        name=collection.name,
        description=collection.description,
        issuer_count=len(rows),
        issuers_with_new_developments=issuers_with_new,
        high_severity_count=high_severity_count,
        new_alert_count=new_alert_count,
        high_severity_alert_count=high_severity_alert_count,
        last_activity_at=last_activity_at,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        contains_issuer=contains_issuer,
    )


def list_watchlists(db: Session, *, issuer_id: UUID | None = None) -> list[WatchlistSummary]:
    collections = collection_repository.list_collections(
        db, collection_type=CollectionType.WATCHLIST
    )
    summaries: list[WatchlistSummary] = []
    for collection in collections:
        rows = _build_rows(db, collection.id)
        contains_issuer = None
        if issuer_id is not None:
            contains_issuer = any(r.issuer_id == issuer_id for r in rows)
        summaries.append(_to_summary(db, collection, rows, contains_issuer=contains_issuer))
    summaries.sort(key=lambda s: s.name)
    return summaries


def get_watchlist(db: Session, watchlist_id: UUID) -> WatchlistSummary | None:
    collection = collection_repository.get_collection(db, watchlist_id)
    if collection is None or collection.collection_type != CollectionType.WATCHLIST:
        return None
    rows = _build_rows(db, watchlist_id)
    return _to_summary(db, collection, rows)


def get_watchlist_detail(db: Session, watchlist_id: UUID) -> WatchlistDetailResponse | None:
    collection = collection_repository.get_collection(db, watchlist_id)
    if collection is None or collection.collection_type != CollectionType.WATCHLIST:
        return None
    rows = _build_rows(db, watchlist_id)
    summary = _to_summary(db, collection, rows)
    return WatchlistDetailResponse(watchlist=summary, issuers=rows)


def create_watchlist(db: Session, *, name: str, description: str) -> WatchlistSummary:
    slug = _unique_slug(db, name)
    collection = collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=slug,
            name=name,
            description=description,
            collection_type=CollectionType.WATCHLIST,
            scope=CollectionScope.PERSONAL,
            curation_method=CurationMethod.USER_CREATED,
            verification_status=VerificationStatus.UNVERIFIED,
        ),
    )
    return _to_summary(db, collection, [])


def update_watchlist(
    db: Session, watchlist_id: UUID, *, name: str | None, description: str | None
) -> WatchlistSummary | None:
    collection = collection_repository.get_collection(db, watchlist_id)
    if collection is None or collection.collection_type != CollectionType.WATCHLIST:
        return None
    updated = collection_repository.update_collection(
        db, watchlist_id, name=name, description=description
    )
    if updated is None:
        return None
    rows = _build_rows(db, watchlist_id)
    return _to_summary(db, updated, rows)


def delete_watchlist(db: Session, watchlist_id: UUID) -> bool:
    """Deletes the Watchlist and its own membership rows only — the
    underlying issuers, securities, evidence, alerts, and Research Universe
    memberships are never touched (`collection_repository.delete_collection`'s
    own guarantee)."""
    collection = collection_repository.get_collection(db, watchlist_id)
    if collection is None or collection.collection_type != CollectionType.WATCHLIST:
        return False
    return collection_repository.delete_collection(db, watchlist_id)


def add_issuer(
    db: Session, watchlist_id: UUID, *, issuer_id: UUID, rationale: str
) -> tuple[WatchlistSummary, bool] | None:
    """Returns `(summary, created)` — `created=False` when the issuer was
    already on this Watchlist (idempotent, never a duplicate-membership
    error). Returns `None` when the Watchlist or issuer doesn't exist, so
    the route can map that to a 404."""
    collection = collection_repository.get_collection(db, watchlist_id)
    if collection is None or collection.collection_type != CollectionType.WATCHLIST:
        return None
    issuer = issuer_repository.get_issuer(db, issuer_id)
    if issuer is None:
        return None

    _membership, created = collection_repository.add_membership(
        db,
        CollectionMembershipCreate(
            collection_id=watchlist_id,
            issuer_id=issuer_id,
            rationale=rationale,
            verification_status=VerificationStatus.UNVERIFIED,
            system_seeded=False,
        ),
    )
    rows = _build_rows(db, watchlist_id)
    return _to_summary(db, collection, rows), created


def remove_issuer(db: Session, watchlist_id: UUID, issuer_id: UUID) -> bool:
    collection = collection_repository.get_collection(db, watchlist_id)
    if collection is None or collection.collection_type != CollectionType.WATCHLIST:
        return False
    return collection_repository.remove_membership(db, watchlist_id, issuer_id)
