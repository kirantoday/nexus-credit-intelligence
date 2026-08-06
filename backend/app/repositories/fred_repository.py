"""Repository for `fred_series_registry` / `fred_observation`.

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.fred import (
    FredObservation,
    FredObservationCreate,
    FredSeriesRegistry,
    FredSeriesRegistryCreate,
)
from app.models.fred import FredObservation as FredObservationModel
from app.models.fred import FredSeriesRegistry as FredSeriesRegistryModel


def _series_to_domain(row: FredSeriesRegistryModel) -> FredSeriesRegistry:
    return FredSeriesRegistry(
        series_id=row.series_id,
        title=row.title,
        category=row.category,
        units=row.units,
        frequency=row.frequency,
        discontinued=row.discontinued,
        redistribution_allowed=row.redistribution_allowed,
        last_synced_at=row.last_synced_at,
    )


def _observation_to_domain(row: FredObservationModel) -> FredObservation:
    return FredObservation(
        id=row.id,
        series_id=row.series_id,
        obs_date=row.obs_date,
        value=row.value,
        provenance_id=row.provenance_id,
    )


def get_series(db: Session, series_id: str) -> FredSeriesRegistry | None:
    row = db.get(FredSeriesRegistryModel, series_id)
    return _series_to_domain(row) if row is not None else None


def upsert_series(db: Session, data: FredSeriesRegistryCreate) -> FredSeriesRegistry:
    """Create the registry row on first sync, or refresh its metadata/`last_synced_at`
    on every later sync — the registry always reflects the most recent sync, not
    just the first one."""
    row = db.get(FredSeriesRegistryModel, data.series_id)
    if row is None:
        row = FredSeriesRegistryModel(series_id=data.series_id)
        db.add(row)
    row.title = data.title
    row.category = data.category
    row.units = data.units
    row.frequency = data.frequency
    row.discontinued = data.discontinued
    row.redistribution_allowed = data.redistribution_allowed
    row.last_synced_at = data.last_synced_at
    db.flush()
    db.refresh(row)
    return _series_to_domain(row)


def get_observation(db: Session, series_id: str, obs_date: date) -> FredObservation | None:
    stmt = select(FredObservationModel).where(
        FredObservationModel.series_id == series_id, FredObservationModel.obs_date == obs_date
    )
    row = db.execute(stmt).scalars().first()
    return _observation_to_domain(row) if row is not None else None


def create_observation(db: Session, data: FredObservationCreate) -> FredObservation:
    row = FredObservationModel(
        series_id=data.series_id,
        obs_date=data.obs_date,
        value=data.value,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _observation_to_domain(row)


def get_latest_observation(db: Session, series_id: str) -> FredObservation | None:
    """Most recent observation for `series_id` — what the Credit Universe's
    benchmark-rate column and the market-context endpoint both read."""
    stmt = (
        select(FredObservationModel)
        .where(FredObservationModel.series_id == series_id)
        .order_by(FredObservationModel.obs_date.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalars().first()
    return _observation_to_domain(row) if row is not None else None
