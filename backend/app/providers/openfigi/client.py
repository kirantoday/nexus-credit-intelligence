"""OpenFIGI HTTP client: fetches and parses `POST /v3/search`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.providers.base.http_client import ThrottledHttpClient
from app.providers.openfigi.dto import OpenFigiSearchResponse

_SEARCH_URL = "https://api.openfigi.com/v3/search"


@dataclass(frozen=True, slots=True)
class SearchFetchResult:
    dto: OpenFigiSearchResponse
    raw_bytes: bytes
    content_type: str
    url: str
    request_body: dict[str, str]
    retrieved_at: datetime


class OpenFigiClient:
    def __init__(self, http_client: ThrottledHttpClient) -> None:
        self._http = http_client

    def search(self, query: str, *, market_sec_des: str = "Corp") -> SearchFetchResult:
        """Search OpenFIGI's reference database by issuer name, optionally
        filtered to a market sector (`"Corp"` for corporate bonds — the only
        one this provider currently uses)."""
        body = {"query": query, "marketSecDes": market_sec_des}
        response = self._http.post_json(_SEARCH_URL, body)
        retrieved_at = datetime.now(UTC)
        dto = OpenFigiSearchResponse.model_validate(json.loads(response.raw_bytes))
        return SearchFetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            url=_SEARCH_URL,
            request_body=body,
            retrieved_at=retrieved_at,
        )
