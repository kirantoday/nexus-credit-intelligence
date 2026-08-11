"""Repository for `alert_event` (PLAN.md section 4.11, 24.3).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import AlertStatus, DetectionMethod, EvidenceSeverity
from app.domain.alert import AlertEvent, AlertEventCreate
from app.models.alert import AlertEvent as AlertEventModel
from app.models.issuer import Issuer as IssuerModel


def _to_domain(row: AlertEventModel) -> AlertEvent:
    return AlertEvent(
        id=row.id,
        issuer_id=row.issuer_id,
        category=row.category,
        severity=EvidenceSeverity(row.severity),
        headline=row.headline,
        explanation=row.explanation,
        evidence_ids=[UUID(eid) for eid in row.evidence_ids],
        bundle_key=row.bundle_key,
        primary_evidence_provider=row.primary_evidence_provider,
        primary_source_label=row.primary_source_label,
        primary_source_url=row.primary_source_url,
        detection_method=DetectionMethod(row.detection_method),
        ai_assisted=row.ai_assisted,
        confidence=float(row.confidence) if row.confidence is not None else None,
        as_of_date=row.as_of_date,
        provenance_id=row.provenance_id,
        status=AlertStatus(row.status),
        acknowledged_at=row.acknowledged_at,
        acknowledged_by=row.acknowledged_by,
        dismissed_at=row.dismissed_at,
        dismissed_by=row.dismissed_by,
        dismissal_reason=row.dismissal_reason,
        is_backfill=row.is_backfill,
        issuer_is_subject=row.issuer_is_subject,
        triggered_at=row.triggered_at,
        created_at=row.created_at,
    )


def create_alert(db: Session, data: AlertEventCreate) -> AlertEvent:
    row = AlertEventModel(
        issuer_id=data.issuer_id,
        category=data.category,
        severity=data.severity.value,
        headline=data.headline,
        explanation=data.explanation,
        evidence_ids=[str(eid) for eid in data.evidence_ids],
        bundle_key=data.bundle_key,
        primary_evidence_provider=data.primary_evidence_provider,
        primary_source_label=data.primary_source_label,
        primary_source_url=data.primary_source_url,
        detection_method=data.detection_method.value,
        ai_assisted=data.ai_assisted,
        confidence=data.confidence,
        as_of_date=data.as_of_date,
        provenance_id=data.provenance_id,
        status=data.status.value,
        is_backfill=data.is_backfill,
        issuer_is_subject=data.issuer_is_subject,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_alert(db: Session, alert_id: UUID) -> AlertEvent | None:
    row = db.get(AlertEventModel, alert_id)
    return _to_domain(row) if row is not None else None


def get_alert_by_bundle_key(db: Session, bundle_key: str) -> AlertEvent | None:
    """Idempotency check for alert synthesis — one alert per evidence bundle,
    ever, regardless of how many times the pipeline re-processes it."""
    stmt = select(AlertEventModel).where(AlertEventModel.bundle_key == bundle_key)
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def list_alerts(
    db: Session,
    *,
    issuer_id: UUID | None = None,
    issuer_ids: list[UUID] | None = None,
    severity: EvidenceSeverity | None = None,
    category: str | None = None,
    evidence_provider: str | None = None,
    status: AlertStatus | None = None,
    detection_method: DetectionMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    triggered_since: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AlertEvent], int]:
    """`date_from`/`date_to` filter by `as_of_date` — the real-world SOURCE
    event date (PLAN.md Milestone 7.5.2 section 8), useful for "alerts
    about events from this calendar period" regardless of when Nexus
    discovered them. `triggered_since` is the other axis entirely — Nexus's
    own PROCESSING time (`triggered_at`) — the one the Morning Research
    Brief's daily-run scoping needs: "alerts Nexus created since the last
    successful daily run," which a March-dated filing discovered today
    correctly satisfies even though its `as_of_date` is months old.

    `issuer_ids` (Milestone 9) filters to a whole set of issuers — e.g. a
    Watchlist's membership — resolved at the SQL level with correct
    pagination/`total`, unlike a fetch-a-page-then-post-filter-in-Python
    approach, which would both misreport `total` and silently drop rows
    off a page. `issuer_id` and `issuer_ids` may both be given (AND
    semantics); no current caller does, but neither excludes the other."""
    stmt = select(AlertEventModel)
    if issuer_id is not None:
        stmt = stmt.where(AlertEventModel.issuer_id == issuer_id)
    if issuer_ids is not None:
        stmt = stmt.where(AlertEventModel.issuer_id.in_(set(issuer_ids)))
    if severity is not None:
        stmt = stmt.where(AlertEventModel.severity == severity.value)
    if category is not None:
        stmt = stmt.where(AlertEventModel.category == category)
    if evidence_provider is not None:
        stmt = stmt.where(AlertEventModel.primary_evidence_provider == evidence_provider)
    if status is not None:
        stmt = stmt.where(AlertEventModel.status == status.value)
    if detection_method is not None:
        stmt = stmt.where(AlertEventModel.detection_method == detection_method.value)
    if date_from is not None:
        stmt = stmt.where(AlertEventModel.as_of_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(AlertEventModel.as_of_date <= date_to)
    if triggered_since is not None:
        stmt = stmt.where(AlertEventModel.triggered_at >= triggered_since)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    paged_stmt = (
        stmt.order_by(AlertEventModel.triggered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(paged_stmt).scalars().all()
    return [_to_domain(row) for row in rows], total


def list_alerts_by_issuer(db: Session, issuer_id: UUID) -> list[AlertEvent]:
    """Every alert for one issuer, unpaginated — bounded by one issuer's
    alert volume (never the whole table), same pattern as
    `research_evidence_repository.list_evidence_by_issuer_and_types`. Backs
    the Issuer Distress Timeline (PLAN.md Milestone 7.5.4), which needs the
    complete history to collapse and order, not a page of it."""
    stmt = select(AlertEventModel).where(AlertEventModel.issuer_id == issuer_id)
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def list_alerts_by_issuers(db: Session, issuer_ids: list[UUID]) -> dict[UUID, list[AlertEvent]]:
    """Batch form of `list_alerts_by_issuer` — one query for many issuers
    instead of one query per issuer, keyed by issuer id. Backs Watchlist
    detail's per-issuer "latest development" / "new developments" columns
    (Milestone 8, PLAN.md 24.9), which would otherwise issue one query per
    watched issuer."""
    if not issuer_ids:
        return {}
    stmt = select(AlertEventModel).where(AlertEventModel.issuer_id.in_(set(issuer_ids)))
    rows = db.execute(stmt).scalars().all()
    result: dict[UUID, list[AlertEvent]] = defaultdict(list)
    for row in rows:
        result[row.issuer_id].append(_to_domain(row))
    return result


def count_alerts_by_severity(
    db: Session,
    *,
    status: AlertStatus | None = None,
    triggered_since: datetime | None = None,
) -> dict[EvidenceSeverity, int]:
    stmt = select(AlertEventModel.severity, func.count()).group_by(AlertEventModel.severity)
    if status is not None:
        stmt = stmt.where(AlertEventModel.status == status.value)
    if triggered_since is not None:
        stmt = stmt.where(AlertEventModel.triggered_at >= triggered_since)
    rows = db.execute(stmt).all()
    return {EvidenceSeverity(severity): count for severity, count in rows}


def count_ai_assisted_alerts(
    db: Session,
    *,
    status: AlertStatus | None = None,
    triggered_since: datetime | None = None,
) -> int:
    stmt = (
        select(func.count())
        .select_from(AlertEventModel)
        .where(AlertEventModel.ai_assisted.is_(True))
    )
    if status is not None:
        stmt = stmt.where(AlertEventModel.status == status.value)
    if triggered_since is not None:
        stmt = stmt.where(AlertEventModel.triggered_at >= triggered_since)
    return db.execute(stmt).scalar_one()


def backfill_issuer_is_subject(
    db: Session, alert_id: UUID, *, issuer_is_subject: bool
) -> AlertEvent:
    """Sets `issuer_is_subject` on an existing alert whose value is
    currently `NULL` (a pre-Milestone-7.5.1 row, or one synthesized without
    an AI review) — used only by `app.scripts.reclassify_system_universes`
    to backfill the field for existing definitive-evidence alerts via a
    fresh, targeted AI re-review, so classification can be corrected
    without rewriting the alert's already-correct, already user-visible
    `headline`/`explanation`/`severity` (PLAN.md Milestone 7.5.1 section 9:
    correct the classification, don't rewrite what was already right)."""
    row = db.get(AlertEventModel, alert_id)
    if row is None:
        raise ValueError(f"alert_event {alert_id} not found")
    row.issuer_is_subject = issuer_is_subject
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def acknowledge_alert(db: Session, alert_id: UUID, *, acknowledged_by: str | None) -> AlertEvent:
    row = db.get(AlertEventModel, alert_id)
    if row is None:
        raise ValueError(f"alert_event {alert_id} not found")
    row.status = AlertStatus.ACKNOWLEDGED.value
    row.acknowledged_at = datetime.now(tz=UTC)
    row.acknowledged_by = acknowledged_by
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def dismiss_alert(
    db: Session, alert_id: UUID, *, dismissed_by: str | None, dismissal_reason: str | None
) -> AlertEvent:
    row = db.get(AlertEventModel, alert_id)
    if row is None:
        raise ValueError(f"alert_event {alert_id} not found")
    row.status = AlertStatus.DISMISSED.value
    row.dismissed_at = datetime.now(tz=UTC)
    row.dismissed_by = dismissed_by
    row.dismissal_reason = dismissal_reason
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def count_alerts(
    db: Session,
    *,
    status: AlertStatus | None = None,
    severity: EvidenceSeverity | None = None,
    issuer_ids: list[UUID] | None = None,
) -> int:
    """Lightweight count-only query for the Alerts Center's summary tiles
    (Milestone 9, PLAN.md 24.11) — deliberately not `list_alerts` with
    `page_size=1`, which would still execute the full filtered query just
    to discard the rows."""
    stmt = select(func.count()).select_from(AlertEventModel)
    if status is not None:
        stmt = stmt.where(AlertEventModel.status == status.value)
    if severity is not None:
        stmt = stmt.where(AlertEventModel.severity == severity.value)
    if issuer_ids is not None:
        stmt = stmt.where(AlertEventModel.issuer_id.in_(set(issuer_ids)))
    return db.execute(stmt).scalar_one()


def search_issuers_with_alerts(
    db: Session, query: str, *, limit: int = 20
) -> list[tuple[UUID, str, str | None]]:
    """Issuer name search scoped to issuers that actually have at least one
    alert (Milestone 9's Alerts Center issuer filter) — the real search
    space for this filter, not every issuer Nexus has ever seen. Returns
    `(issuer_id, legal_name, ticker)` tuples, distinct, name-ordered."""
    pattern = f"%{query}%"
    stmt = (
        select(IssuerModel.id, IssuerModel.legal_name, IssuerModel.ticker)
        .join(AlertEventModel, AlertEventModel.issuer_id == IssuerModel.id)
        .where(IssuerModel.legal_name.ilike(pattern))
        .distinct()
        .order_by(IssuerModel.legal_name.asc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [(row[0], row[1], row[2]) for row in rows]
