"""ORM model for the durable raw-response store (PLAN.md section 4.4).

`provenance_id` and `provenance.raw_payload_id` reference each other (a real,
intentional circular FK per the schema — see PLAN.md 4.1/4.4). `use_alter=True`
tells Alembic/SQLAlchemy to create this table's FK as a separate `ALTER TABLE
... ADD CONSTRAINT` after both tables exist, rather than failing to resolve a
create-order cycle.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import ProviderName
from app.db.base import Base

_PROVIDER_SQL_LIST = ", ".join(f"'{value}'" for value in ProviderName)


class RawProviderPayload(Base):
    __tablename__ = "raw_provider_payload"
    __table_args__ = (
        CheckConstraint(
            f"provider IN ({_PROVIDER_SQL_LIST})", name="ck_raw_provider_payload_provider"
        ),
        CheckConstraint(
            "payload_json IS NOT NULL OR storage_object_path IS NOT NULL",
            name="ck_raw_provider_payload_has_storage_location",
        ),
        Index("ix_raw_provider_payload_provider_fingerprint", "provider", "request_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSONB, nullable=True)
    storage_object_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("provenance.id", use_alter=True, name="fk_raw_provider_payload_provenance_id"),
        nullable=True,
    )
