"""Unit tests for app/providers/fred/normalizer.py."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.types import DataClassification, ProviderName, TransformationType
from app.providers.fred.dto import FredObservationEntry, FredSeriesInfo
from app.providers.fred.normalizer import (
    is_missing_observation,
    normalize_observation,
    normalize_observation_provenance,
    normalize_series_registry,
)


def test_is_missing_observation_true_for_fred_missing_marker() -> None:
    assert is_missing_observation(FredObservationEntry(date="2026-07-04", value=".")) is True


def test_is_missing_observation_false_for_a_real_value() -> None:
    assert is_missing_observation(FredObservationEntry(date="2026-08-05", value="3.64")) is False


def test_normalize_observation_parses_decimal_value() -> None:
    entry = FredObservationEntry(date="2026-08-05", value="3.64")
    observation = normalize_observation(entry, series_id="SOFR", provenance_id=uuid4())
    assert observation.series_id == "SOFR"
    assert observation.obs_date == date(2026, 8, 5)
    assert observation.value == Decimal("3.64")


def test_normalize_observation_raises_on_unparseable_value() -> None:
    entry = FredObservationEntry(date="2026-08-05", value="not-a-number")
    with pytest.raises(ValueError, match="unparseable FRED observation value"):
        normalize_observation(entry, series_id="SOFR", provenance_id=uuid4())


def test_normalize_observation_provenance_is_public_reported_fred() -> None:
    entry = FredObservationEntry(date="2026-08-05", value="3.64")
    retrieved_at = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)
    provenance = normalize_observation_provenance(
        entry,
        series_id="SOFR",
        source_url="https://api.stlouisfed.org/fred/series/observations",
        retrieved_at=retrieved_at,
        raw_payload_id=uuid4(),
    )
    assert provenance.provider is ProviderName.FRED
    assert provenance.source_record_id == "SOFR:2026-08-05"
    assert provenance.as_of_date == date(2026, 8, 5)
    assert provenance.classification is DataClassification.PUBLIC
    assert provenance.transformation is TransformationType.REPORTED


def test_normalize_series_registry_uses_curator_category_not_api_field() -> None:
    """FRED's real `/fred/series` response has no `category` field — this
    must come from the caller-supplied label, not something parsed off `info`."""
    info = FredSeriesInfo(
        id="SOFR",
        title="Secured Overnight Financing Rate",
        units="Percent",
        frequency="Daily",
        observation_start="2018-04-03",
        observation_end="2026-08-05",
        last_updated="2026-08-06 07:02:15-05",
    )
    now = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)
    registry = normalize_series_registry(info, category="rates", now=now)
    assert registry.series_id == "SOFR"
    assert registry.category == "rates"
    assert registry.units == "Percent"
    assert registry.frequency == "Daily"
    assert registry.discontinued is False
    assert registry.redistribution_allowed is True
    assert registry.last_synced_at == now
