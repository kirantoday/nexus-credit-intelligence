"""FRED HTTP client: fetches and parses series metadata + observations.

PLAN.md section 4.1 is explicit that `provenance.source_url` carries "no API
keys embedded" — every fetch method here returns a `public_url` (no
`api_key` query param) for that purpose, separate from the actual
key-bearing request URL used only for the HTTP call itself. The API key is
never written to a log line, an f-string passed to a raised exception, or
any persisted field in this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar
from urllib.parse import urlencode

from app.providers.base.http_client import ThrottledHttpClient
from app.providers.fred.dto import FredObservationsResponse, FredSeriesResponse

_SERIES_URL = "https://api.stlouisfed.org/fred/series"
_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"

_DtoT = TypeVar("_DtoT")


@dataclass(frozen=True, slots=True)
class FetchResult(Generic[_DtoT]):
    dto: _DtoT
    raw_bytes: bytes
    content_type: str
    public_url: str
    retrieved_at: datetime


class FredClient:
    def __init__(self, http_client: ThrottledHttpClient, *, api_key: str) -> None:
        if not api_key:
            raise ValueError("api_key is required for FRED requests")
        self._http = http_client
        self._api_key = api_key

    def fetch_series(self, series_id: str) -> FetchResult[FredSeriesResponse]:
        public_params = {"series_id": series_id, "file_type": "json"}
        request_url = f"{_SERIES_URL}?{urlencode({**public_params, 'api_key': self._api_key})}"
        response = self._http.get(request_url)
        retrieved_at = datetime.now(UTC)
        dto = FredSeriesResponse.model_validate(json.loads(response.raw_bytes))
        return FetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            public_url=f"{_SERIES_URL}?{urlencode(public_params)}",
            retrieved_at=retrieved_at,
        )

    def fetch_observations(
        self, series_id: str, *, limit: int = 10
    ) -> FetchResult[FredObservationsResponse]:
        public_params = {
            "series_id": series_id,
            "file_type": "json",
            "sort_order": "desc",
            "limit": str(limit),
        }
        request_url = (
            f"{_OBSERVATIONS_URL}?{urlencode({**public_params, 'api_key': self._api_key})}"
        )
        response = self._http.get(request_url)
        retrieved_at = datetime.now(UTC)
        dto = FredObservationsResponse.model_validate(json.loads(response.raw_bytes))
        return FetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            public_url=f"{_OBSERVATIONS_URL}?{urlencode(public_params)}",
            retrieved_at=retrieved_at,
        )
