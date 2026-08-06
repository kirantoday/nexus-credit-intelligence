"""ORM models for `fred_series_registry` / `fred_observation` (PLAN.md section 4.5)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FredSeriesRegistry(Base):
    __tablename__ = "fred_series_registry"

    series_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    units: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(Text, nullable=False)
    discontinued: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    redistribution_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FredObservation(Base):
    __tablename__ = "fred_observation"
    __table_args__ = (
        Index("ix_fred_observation_series_id", "series_id"),
        Index("ix_fred_observation_provenance_id", "provenance_id"),
        # Idempotency: re-syncing a series should not duplicate a date's observation.
        Index("ix_fred_observation_dedup", "series_id", "obs_date", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    series_id: Mapped[str] = mapped_column(
        Text, ForeignKey("fred_series_registry.series_id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
