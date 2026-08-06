"""FRED DTO -> canonical domain object mapping.

The only place FRED-specific shapes get translated into PLAN.md's
provider-neutral canonical schema (`app/domain/fred.py`).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.core.types import DataClassification, ProviderName, TransformationType
from app.domain.fred import FredObservationCreate, FredSeriesRegistryCreate
from app.domain.provenance import ProvenanceCreate
from app.providers.fred.dto import FredObservationEntry, FredSeriesInfo

# FRED's real "." missing-observation marker (holidays, pre-series-start
# dates, etc.) — verified live, not assumed. See `app/domain/fred.py`'s
# `FredObservationCreate` docstring for why these become no row, not a
# fabricated/null one.
_MISSING_VALUE_MARKER = "."


def normalize_series_registry(
    info: FredSeriesInfo, *, category: str, now: datetime
) -> FredSeriesRegistryCreate:
    """`category` is a curator-assigned label (e.g. "rates",
    "credit_spreads"), not something FRED's `/fred/series` response
    contains — see `app/domain/fred.py`'s module docstring."""
    return FredSeriesRegistryCreate(
        series_id=info.id,
        title=info.title,
        category=category,
        units=info.units,
        frequency=info.frequency,
        discontinued=False,
        redistribution_allowed=True,
        last_synced_at=now,
    )


def normalize_observation_provenance(
    entry: FredObservationEntry,
    *,
    series_id: str,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.FRED,
        source_record_id=f"{series_id}:{entry.date}",
        source_url=source_url,
        as_of_date=date.fromisoformat(entry.date),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def is_missing_observation(entry: FredObservationEntry) -> bool:
    """True for FRED's missing-observation marker (see module docstring) —
    checked before any provenance row is created for `entry`, so a missing
    date never gets a wasted `provenance` row pointing at nothing."""
    return entry.value == _MISSING_VALUE_MARKER


def normalize_observation(
    entry: FredObservationEntry, *, series_id: str, provenance_id: UUID
) -> FredObservationCreate:
    """Caller must have already skipped `is_missing_observation(entry)` —
    this always produces a row, never returns `None`."""
    try:
        value = Decimal(entry.value)
    except InvalidOperation:
        # Real FRED data has only ever shown numeric strings or "."; a third
        # shape would be a genuine provider-format surprise, not a case to
        # paper over by guessing a value.
        raise ValueError(f"unparseable FRED observation value: {entry.value!r}") from None
    return FredObservationCreate(
        series_id=series_id,
        obs_date=date.fromisoformat(entry.date),
        value=value,
        provenance_id=provenance_id,
    )
