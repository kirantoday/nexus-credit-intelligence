"""Repository for `alert_event` (PLAN.md section 4.11, 24.3).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import AlertStatus, DetectionMethod, EvidenceSeverity
from app.domain.alert import AlertEvent, AlertEventCreate
from app.models.alert import AlertEvent as AlertEventModel


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
    severity: EvidenceSeverity | None = None,
    category: str | None = None,
    evidence_provider: str | None = None,
    status: AlertStatus | None = None,
    detection_method: DetectionMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AlertEvent], int]:
    stmt = select(AlertEventModel)
    if issuer_id is not None:
        stmt = stmt.where(AlertEventModel.issuer_id == issuer_id)
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

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    paged_stmt = (
        stmt.order_by(AlertEventModel.triggered_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(paged_stmt).scalars().all()
    return [_to_domain(row) for row in rows], total


def count_alerts_by_severity(
    db: Session,
    *,
    status: AlertStatus | None = None,
) -> dict[EvidenceSeverity, int]:
    stmt = select(AlertEventModel.severity, func.count()).group_by(AlertEventModel.severity)
    if status is not None:
        stmt = stmt.where(AlertEventModel.status == status.value)
    rows = db.execute(stmt).all()
    return {EvidenceSeverity(severity): count for severity, count in rows}


def count_ai_assisted_alerts(
    db: Session,
    *,
    status: AlertStatus | None = None,
) -> int:
    stmt = (
        select(func.count())
        .select_from(AlertEventModel)
        .where(AlertEventModel.ai_assisted.is_(True))
    )
    if status is not None:
        stmt = stmt.where(AlertEventModel.status == status.value)
    return db.execute(stmt).scalar_one()


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
