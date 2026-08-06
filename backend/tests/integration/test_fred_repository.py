"""Integration tests for fred_repository against the live nexus schema."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.fred import FredObservationCreate, FredSeriesRegistryCreate
from app.repositories import fred_repository, provenance_repository
from tests.integration.conftest import reported_public_provenance


def _seed_series(db: Session, *, series_id: str) -> None:
    fred_repository.upsert_series(
        db,
        FredSeriesRegistryCreate(
            series_id=series_id,
            title="Test Series",
            category="rates",
            units="Percent",
            frequency="Daily",
            last_synced_at=datetime.now(UTC),
        ),
    )


def test_upsert_series_creates_then_updates(db_session: Session) -> None:
    _seed_series(db_session, series_id="TEST_SERIES_1")
    first = fred_repository.get_series(db_session, "TEST_SERIES_1")
    assert first is not None
    assert first.title == "Test Series"

    fred_repository.upsert_series(
        db_session,
        FredSeriesRegistryCreate(
            series_id="TEST_SERIES_1",
            title="Updated Title",
            category="rates",
            units="Percent",
            frequency="Daily",
            last_synced_at=datetime.now(UTC),
        ),
    )
    second = fred_repository.get_series(db_session, "TEST_SERIES_1")
    assert second is not None
    assert second.title == "Updated Title"


def test_create_observation_and_get_by_series_and_date(db_session: Session) -> None:
    _seed_series(db_session, series_id="TEST_SERIES_2")
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())

    created = fred_repository.create_observation(
        db_session,
        FredObservationCreate(
            series_id="TEST_SERIES_2",
            obs_date=date(2026, 8, 5),
            value=Decimal("3.64"),
            provenance_id=provenance.id,
        ),
    )

    fetched = fred_repository.get_observation(db_session, "TEST_SERIES_2", date(2026, 8, 5))
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.value == Decimal("3.64")


def test_get_observation_returns_none_when_missing(db_session: Session) -> None:
    _seed_series(db_session, series_id="TEST_SERIES_3")
    assert fred_repository.get_observation(db_session, "TEST_SERIES_3", date(2099, 1, 1)) is None


def test_get_latest_observation_returns_most_recent_date(db_session: Session) -> None:
    _seed_series(db_session, series_id="TEST_SERIES_4")
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())

    for obs_date, value in [
        (date(2026, 8, 3), Decimal("3.65")),
        (date(2026, 8, 5), Decimal("3.64")),
        (date(2026, 8, 4), Decimal("3.66")),
    ]:
        fred_repository.create_observation(
            db_session,
            FredObservationCreate(
                series_id="TEST_SERIES_4",
                obs_date=obs_date,
                value=value,
                provenance_id=provenance.id,
            ),
        )

    latest = fred_repository.get_latest_observation(db_session, "TEST_SERIES_4")
    assert latest is not None
    assert latest.obs_date == date(2026, 8, 5)
    assert latest.value == Decimal("3.64")


def test_get_latest_observation_returns_none_for_unknown_series(db_session: Session) -> None:
    assert fred_repository.get_latest_observation(db_session, "NO_SUCH_SERIES") is None
