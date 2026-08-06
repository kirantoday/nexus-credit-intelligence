"""ORM model for the entitlement engine's data (PLAN.md section 4.8).

`policy_check()` (app/core/entitlement.py) is a pure function operating on a
`DataEntitlement` domain object — this table is what a repository loads to
produce that domain object, never queried from `policy_check()` itself.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Date, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import EnvironmentName, ProviderName
from app.db.base import Base

_PROVIDER_SQL_LIST = ", ".join(f"'{value}'" for value in ProviderName)
_ENVIRONMENT_SQL_LIST = ", ".join(f"'{value}'" for value in EnvironmentName)


class DataEntitlement(Base):
    __tablename__ = "data_entitlement"
    __table_args__ = (
        CheckConstraint(f"provider IN ({_PROVIDER_SQL_LIST})", name="ck_data_entitlement_provider"),
        CheckConstraint(
            f"environment IN ({_ENVIRONMENT_SQL_LIST})", name="ck_data_entitlement_environment"
        ),
        CheckConstraint(
            "expiration_date IS NULL OR expiration_date >= effective_date",
            name="ck_data_entitlement_date_range",
        ),
        Index(
            "ix_data_entitlement_lookup",
            "provider",
            "dataset",
            "legal_entity",
            "environment",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    dataset: Mapped[str] = mapped_column(Text, nullable=False)
    legal_entity: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    permitted_users: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    permitted_use: Mapped[str] = mapped_column(Text, nullable=False)
    storage_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retention_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    derived_data_permission: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ai_processing_permission: Mapped[bool] = mapped_column(Boolean, nullable=False)
    embedding_permission: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_permission: Mapped[bool] = mapped_column(Boolean, nullable=False)
    redistribution_permission: Mapped[bool] = mapped_column(Boolean, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_reference: Mapped[str] = mapped_column(Text, nullable=False)
