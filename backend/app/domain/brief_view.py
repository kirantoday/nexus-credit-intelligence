"""Canonical domain object for `morning_brief_view` (PLAN.md Milestone 7.5.2
correction — user-relative Morning Brief boundary).

See `app/models/brief_view.py` for why this is a single shared timeline
rather than a per-user one.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BriefView(BaseModel):
    """A persisted `morning_brief_view` row."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    viewed_at: datetime
    created_at: datetime
