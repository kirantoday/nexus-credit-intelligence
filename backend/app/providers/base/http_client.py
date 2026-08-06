"""Generic throttled HTTP client for provider adapters.

Provider APIs (SEC EDGAR now; FRED/CourtListener/OpenFIGI later) have fair-use
rate limits and require a descriptive User-Agent identifying the caller — SEC
in particular blocks IPs that send a generic/browser-like User-Agent or exceed
its published rate limit. This wraps `httpx` with both concerns handled once,
so no provider adapter has to reimplement either.

Deliberately returns raw bytes, not parsed JSON: different provider responses
need different JSON-parsing options (e.g. SEC EDGAR company facts need
`parse_float=Decimal` to avoid binary-float precision loss on financial
values — see `sec_edgar/client.py`), and the raw bytes are also exactly what
gets checksummed and persisted verbatim to `raw_provider_payload`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import TracebackType

import httpx


@dataclass(frozen=True, slots=True)
class HttpResponse:
    raw_bytes: bytes
    content_type: str
    status_code: int


class ThrottledHttpClient:
    """A synchronous HTTP GET client with a minimum delay between requests.

    Synchronous, not async: matches this project's synchronous SQLAlchemy
    session (PLAN.md Technical Debt TD-004) and keeps provider adapters
    simple. Revisit together if either becomes a real bottleneck.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        min_interval_seconds: float = 0.15,
        timeout_seconds: float = 30.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not user_agent:
            raise ValueError("user_agent is required for provider HTTP requests")
        self._min_interval_seconds = min_interval_seconds
        headers = {"User-Agent": user_agent, "Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        self._client = httpx.Client(timeout=timeout_seconds, headers=headers)
        self._last_request_at: float | None = None

    def get(self, url: str) -> HttpResponse:
        self._throttle()
        response = self._client.get(url)
        response.raise_for_status()
        return HttpResponse(
            raw_bytes=response.content,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            status_code=response.status_code,
        )

    def post_json(self, url: str, json_body: object) -> HttpResponse:
        """POST with a JSON body (e.g. OpenFIGI's search/mapping endpoints,
        which take their query as a POST body rather than query params)."""
        self._throttle()
        response = self._client.post(url, json=json_body)
        response.raise_for_status()
        return HttpResponse(
            raw_bytes=response.content,
            content_type=response.headers.get("content-type", "application/octet-stream"),
            status_code=response.status_code,
        )

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            remaining = self._min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ThrottledHttpClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
