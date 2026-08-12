"""ORM model for `audit_event` (PLAN.md 4.12; Milestone 10A — PLAN.md 24.12).

The first concrete audited-write path in the app (research notes) — sets the
pattern later milestones follow for watchlist changes, alert-rule changes,
entitlement changes, admin actions, and AI queries touching restricted data
(PLAN.md 4.12's full scope, not all populated yet).

`event_type`/`entity_table` are deliberately left as unconstrained `text`
columns rather than CHECK-constrained enums (contrast `research_note.
thesis_status` etc.) — see `app.core.types.AuditEventType`'s docstring for
why: this table's future writers span many unrelated milestones, and a
CHECK constraint would force a migration every time one of them adds a new
audited action. `before_state`/`after_state` are separate JSONB columns
(not one opaque `detail` blob) so "what changed" is inspectable without the
caller having to agree on an internal shape.

`user_id` is nullable — Milestone 10A has no `user` table and
`AUTH_ENABLED=false` (a single shared analyst workspace, per TD-002/
ADR-016's already-established `owner_user_id=NULL` convention). System-
initiated events (e.g. a future scheduled job) also leave it null rather
than attributing to a fabricated actor.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_entity", "entity_table", "entity_id"),
        Index("ix_audit_event_occurred_at", "occurred_at"),
        Index("ix_audit_event_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_table: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    before_state: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    # `clock_timestamp()`, not `now()`: `now()` is frozen at transaction
    # start, so two audit events written in the same transaction (e.g. a
    # test fixture reusing one connection across several service calls)
    # would get an identical timestamp and an unstable relative order.
    # `clock_timestamp()` reflects actual statement execution time, giving
    # every audit event a genuinely distinct, correctly-orderable instant.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
