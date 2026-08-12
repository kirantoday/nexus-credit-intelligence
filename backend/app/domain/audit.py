"""Canonical domain objects for `audit_event` (PLAN.md 4.12; Milestone 10A).

See `app.models.audit`'s module docstring for why `event_type`/
`entity_table` are plain `str` here rather than a closed enum.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventCreate(BaseModel):
    """Everything needed to create an `audit_event` row; id/`occurred_at`
    are server-generated."""

    model_config = ConfigDict(frozen=True)

    user_id: str | None = None
    event_type: str
    entity_table: str
    entity_id: UUID | None = None
    before_state: dict[str, object] | None = None
    after_state: dict[str, object] | None = None


class AuditEvent(BaseModel):
    """A persisted `audit_event` row."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: str | None
    event_type: str
    entity_table: str
    entity_id: UUID | None
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    occurred_at: datetime
