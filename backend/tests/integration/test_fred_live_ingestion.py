"""Live, end-to-end proof of Milestone 5's FRED slice (PLAN.md section 18
step 5): "what macroeconomic environment surrounds this credit?" — a genuine
live sync of a real FRED series (SOFR), with raw payloads and provenance
preserved for every observation.

Skipped gracefully (not failed) if SEC_USER_AGENT, FRED_API_KEY, or
DATABASE_URL isn't configured. Runs inside the same rolled-back transaction
as every other integration test; reads here see whatever FRED data was
already genuinely committed too (Milestone 5 left real SOFR/HY OAS
observations permanently in the database — see BUILD_LOG.md), so these tests
assert data correctness and idempotency, not a fixed created/found count —
same pattern as `test_openfigi_live_ingestion.py` and
`test_sec_edgar_live_ingestion.py`.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.types import DataClassification, ProviderName, TransformationType
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.fred.provider import sync_series
from app.repositories import provenance_repository, raw_provider_payload_repository

_SERIES_ID = "SOFR"


def test_live_sync_series_returns_real_observations(
    db_session: Session, fred_http_client: ThrottledHttpClient, fred_api_key: str
) -> None:
    result = sync_series(
        db_session,
        fred_http_client,
        api_key=fred_api_key,
        series_id=_SERIES_ID,
        category="rates",
        limit=5,
    )

    assert result.series.series_id == _SERIES_ID
    assert result.series.title == "Secured Overnight Financing Rate"
    assert result.series.units == "Percent"
    assert result.series.category == "rates"

    assert len(result.observations) > 0
    for entry in result.observations:
        assert entry.observation.series_id == _SERIES_ID
        assert entry.observation.value > Decimal(0)
        assert entry.observation.value < Decimal(100)  # a real rate, not a fabricated/garbage one


def test_live_sync_series_is_idempotent_per_observation(
    db_session: Session, fred_http_client: ThrottledHttpClient, fred_api_key: str
) -> None:
    first = sync_series(
        db_session,
        fred_http_client,
        api_key=fred_api_key,
        series_id=_SERIES_ID,
        category="rates",
        limit=5,
    )
    second = sync_series(
        db_session,
        fred_http_client,
        api_key=fred_api_key,
        series_id=_SERIES_ID,
        category="rates",
        limit=5,
    )

    first_by_date = {
        entry.observation.obs_date: entry.observation.id for entry in first.observations
    }
    for entry in second.observations:
        assert entry.observation.id == first_by_date[entry.observation.obs_date]
        # Re-syncing the exact same dates in the same transaction must never
        # report them as newly created the second time.
        assert entry.observation_created is False


def test_live_sync_series_persists_raw_payload_and_provenance(
    db_session: Session, fred_http_client: ThrottledHttpClient, fred_api_key: str
) -> None:
    result = sync_series(
        db_session,
        fred_http_client,
        api_key=fred_api_key,
        series_id=_SERIES_ID,
        category="rates",
        limit=3,
    )
    assert len(result.observations) > 0
    observation = result.observations[0].observation

    provenance = provenance_repository.get_provenance(db_session, observation.provenance_id)
    assert provenance is not None
    assert provenance.provider is ProviderName.FRED
    assert provenance.classification is DataClassification.PUBLIC
    assert provenance.transformation is TransformationType.REPORTED
    assert provenance.as_of_date == observation.obs_date
    assert provenance.raw_payload_id is not None

    raw_payload = raw_provider_payload_repository.get_payload(db_session, provenance.raw_payload_id)
    assert raw_payload is not None
    assert raw_payload.provider is ProviderName.FRED
    assert raw_payload.payload_json is not None
    # The API key must never leak into anything persisted — not the raw
    # payload (FRED's own response never contains the caller's key) and not
    # the request fingerprint (a hash, not the URL itself).
    assert "api_key" not in str(raw_payload.payload_json)
