"""Canonical domain objects for `fred_series_registry` / `fred_observation` (PLAN.md section 4.5).

`category`, `discontinued`, and `redistribution_allowed` on `FredSeriesRegistryCreate`
are deliberately NOT parsed from FRED's `/fred/series` response — that endpoint
doesn't return any of the three as structured fields (verified live before
writing this). `category` is a curator-assigned label describing why *we*
sync this series (e.g. "rates", "credit_spreads"), not a FRED-reported fact.
`discontinued`/`redistribution_allowed` are sync-time defaults reflecting
known reality (both series ingested in Milestone 5 are actively updating;
FRED's general terms permit attributed redistribution of its public series) —
not values read off any single API field. See `providers/fred/normalizer.py`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FredSeriesRegistryCreate(BaseModel):
    """Everything needed to create/update a `fred_series_registry` row.

    `series_id` (FRED's own stable identifier, e.g. "SOFR") is the primary
    key — no separate surrogate id, matching PLAN.md 4.5's column list, which
    lists `series_id` first with no accompanying `id`.
    """

    model_config = ConfigDict(frozen=True)

    series_id: str
    title: str
    category: str | None = None
    units: str
    frequency: str
    discontinued: bool = False
    redistribution_allowed: bool = True
    last_synced_at: datetime


class FredSeriesRegistry(FredSeriesRegistryCreate):
    """A persisted `fred_series_registry` row."""


class FredObservationCreate(BaseModel):
    """Everything needed to create a `fred_observation` row; id is server-generated.

    No row is ever created for a FRED "missing" observation (API value `"."`)
    — a missing data point is the honest absence of a fact for that date, not
    a fact with a null value (`providers/fred/normalizer.py` filters these
    out before this object is ever constructed).
    """

    model_config = ConfigDict(frozen=True)

    series_id: str
    obs_date: date
    value: Decimal
    provenance_id: UUID


class FredObservation(FredObservationCreate):
    """A persisted `fred_observation` row."""

    id: UUID
