"""FRED provider orchestration: fetch -> persist raw payload -> normalize -> persist canonical.

Same pipeline shape as `sec_edgar/provider.py` / `openfigi/provider.py`.
Never opens a session or calls the ORM directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.fred import FredObservation, FredSeriesRegistry
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.fred import normalizer
from app.providers.fred.client import FredClient
from app.repositories import fred_repository, provenance_repository


@dataclass(frozen=True, slots=True)
class ObservationSyncResult:
    observation: FredObservation
    observation_created: bool


@dataclass(frozen=True, slots=True)
class FredSyncResult:
    series: FredSeriesRegistry
    observations: list[ObservationSyncResult]


def sync_series(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    api_key: str,
    series_id: str,
    category: str,
    limit: int = 10,
) -> FredSyncResult:
    """Sync one FRED series' metadata and its most recent `limit`
    observations (PLAN.md section 18 step 5's "what macroeconomic
    environment surrounds this credit?").

    Not a bulk historical loader by design — a first vertical slice needs
    enough recent history to be useful (a benchmark-rate column, a market
    snapshot), not a full backfill to `observation_start`. Idempotent per
    observation via `(series_id, obs_date)`'s unique index; every call still
    fetches fresh and logs new `raw_provider_payload` rows, matching this
    project's audit-trail convention.
    """
    client = FredClient(http_client, api_key=api_key)

    series_fetch = client.fetch_series(series_id)
    raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.FRED,
        source_record_id=series_id,
        url=series_fetch.public_url,
        raw_bytes=series_fetch.raw_bytes,
        payload_json=json.loads(series_fetch.raw_bytes),
        content_type=series_fetch.content_type,
        retrieved_at=series_fetch.retrieved_at,
    )
    if not series_fetch.dto.seriess:
        raise ValueError(f"FRED series {series_id!r} not found")
    series = fred_repository.upsert_series(
        db,
        normalizer.normalize_series_registry(
            series_fetch.dto.seriess[0], category=category, now=series_fetch.retrieved_at
        ),
    )

    obs_fetch = client.fetch_observations(series_id, limit=limit)
    obs_payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.FRED,
        source_record_id=series_id,
        url=obs_fetch.public_url,
        raw_bytes=obs_fetch.raw_bytes,
        payload_json=json.loads(obs_fetch.raw_bytes),
        content_type=obs_fetch.content_type,
        retrieved_at=obs_fetch.retrieved_at,
    )

    results: list[ObservationSyncResult] = []
    for entry in obs_fetch.dto.observations:
        if normalizer.is_missing_observation(entry):
            # A real FRED "." missing observation (e.g. a holiday on a daily
            # series) — no row for it at all, not even a "found existing"
            # one; see normalizer.py.
            continue

        existing = fred_repository.get_observation(db, series_id, date.fromisoformat(entry.date))
        if existing is not None:
            results.append(ObservationSyncResult(observation=existing, observation_created=False))
            continue

        obs_provenance = provenance_repository.create_provenance(
            db,
            normalizer.normalize_observation_provenance(
                entry,
                series_id=series_id,
                source_url=obs_fetch.public_url,
                retrieved_at=obs_fetch.retrieved_at,
                raw_payload_id=obs_payload.id,
            ),
        )
        observation = fred_repository.create_observation(
            db,
            normalizer.normalize_observation(
                entry, series_id=series_id, provenance_id=obs_provenance.id
            ),
        )
        results.append(ObservationSyncResult(observation=observation, observation_created=True))

    return FredSyncResult(series=series, observations=results)
