"""Repository for `audit_event` (PLAN.md 4.12; Milestone 10A).

Function-style, domain objects only, flush-not-commit — see
`provenance_repository.py`'s module docstring for this project's repository
conventions.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.audit import AuditEvent, AuditEventCreate
from app.models.audit import AuditEvent as AuditEventModel


def _to_domain(row: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        user_id=row.user_id,
        event_type=row.event_type,
        entity_table=row.entity_table,
        entity_id=row.entity_id,
        before_state=row.before_state,
        after_state=row.after_state,
        occurred_at=row.occurred_at,
    )


def create_event(db: Session, data: AuditEventCreate) -> AuditEvent:
    row = AuditEventModel(
        user_id=data.user_id,
        event_type=data.event_type,
        entity_table=data.entity_table,
        entity_id=data.entity_id,
        before_state=data.before_state,
        after_state=data.after_state,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def list_events_for_entity(db: Session, entity_table: str, entity_id: UUID) -> list[AuditEvent]:
    stmt = (
        select(AuditEventModel)
        .where(
            AuditEventModel.entity_table == entity_table,
            AuditEventModel.entity_id == entity_id,
        )
        .order_by(AuditEventModel.occurred_at.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
