"""ORM model for `morning_brief_view` (PLAN.md Milestone 7.5.2 correction).

An append-only log of "the Morning Research Brief was viewed" events —
deliberately a single shared timeline, not per-user, since Nexus has no
authentication/session infrastructure yet (TD-002). One row is added per
genuinely new viewing occasion (gated by a minimum gap in the service layer,
`app.services.morning_brief_service`, not here); the model itself imposes no
business rule beyond "this happened at this time."
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BriefView(Base):
    __tablename__ = "morning_brief_view"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
