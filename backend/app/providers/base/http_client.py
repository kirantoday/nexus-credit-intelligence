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
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType

import httpx


@dataclass(frozen=True, slots=True)
class HttpResponse:
    raw_bytes: bytes
    content_type: str
    status_code: int


class RetryAfterTooLongError(Exception):
    """A provider's `Retry-After` (or the default fallback) exceeded this
    client's configured `max_retry_after_seconds` (PLAN.md Milestone 7.5.3
    — the CourtListener incident this fixes: a single retry wait blocked
    an entire live discovery batch for 4+ hours because nothing capped how
    long `get()` would `time.sleep()` for). Raised instead of sleeping —
    callers already isolate provider failures per-issuer/per-provider
    (`enrichment_orchestrator.enrich_issuer`'s try/except marks
    `FAILED_RETRYABLE` with a `next_retry_at`), so this becomes "retryable,
    try again later" rather than a multi-hour stall of unrelated work.
    """

    def __init__(self, *, requested_seconds: float, max_seconds: float) -> None:
        self.requested_seconds = requested_seconds
        self.max_seconds = max_seconds
        super().__init__(
            f"Retry-After requested {requested_seconds:.1f}s, exceeding this client's "
            f"max_retry_after_seconds={max_seconds:.1f}s ceiling — not waited, treated as a "
            "retryable failure instead of stalling the caller."
        )


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
        retry_on_status: frozenset[int] = frozenset(),
        max_retries: int = 0,
        default_retry_after_seconds: float = 15.0,
        max_retry_after_seconds: float = 120.0,
    ) -> None:
        if not user_agent:
            raise ValueError("user_agent is required for provider HTTP requests")
        self._min_interval_seconds = min_interval_seconds
        headers = {"User-Agent": user_agent, "Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        self._client = httpx.Client(timeout=timeout_seconds, headers=headers)
        self._last_request_at: float | None = None
        # Opt-in: every existing caller (SEC EDGAR/OpenFIGI/FRED) passes
        # neither, so `get()` raises on the first non-2xx exactly as before.
        # Added for CourtListener (Milestone 7), whose real, live-observed
        # throttle (429 "Rate limit exceeded: 10/min") this project's own
        # conservative per-request interval doesn't always avoid under a
        # shared token.
        self._retry_on_status = retry_on_status
        self._max_retries = max_retries
        self._default_retry_after_seconds = default_retry_after_seconds
        # Hard ceiling on any single retry wait, regardless of what a
        # provider's `Retry-After` header requests or what the fallback
        # default is — see `RetryAfterTooLongError`.
        self._max_retry_after_seconds = max_retry_after_seconds

    def get(self, url: str) -> HttpResponse:
        for attempt in range(self._max_retries + 1):
            self._throttle()
            response = self._client.get(url)
            if response.status_code in self._retry_on_status and attempt < self._max_retries:
                wait_seconds = self._retry_after_seconds(response)
                if wait_seconds > self._max_retry_after_seconds:
                    raise RetryAfterTooLongError(
                        requested_seconds=wait_seconds, max_seconds=self._max_retry_after_seconds
                    )
                time.sleep(wait_seconds)
                continue
            response.raise_for_status()
            return HttpResponse(
                raw_bytes=response.content,
                content_type=response.headers.get("content-type", "application/octet-stream"),
                status_code=response.status_code,
            )
        raise AssertionError("unreachable: loop always returns or raises")

    def _retry_after_seconds(self, response: httpx.Response) -> float:
        """RFC 7231 §7.1.3: `Retry-After` is either delta-seconds (an
        integer) or an HTTP-date. Milestone 7.5.3's live-caught bug: this
        used to do a bare `float(header_value)` — which happens to parse a
        stray digit-only HTTP-date fragment or any other unexpectedly huge
        numeric string as a gigantic delta-seconds count with no sanity
        check, producing a `time.sleep()` of hours. Both valid forms are
        parsed correctly here; anything else (unparseable, negative, or
        simply absurd) falls back to `default_retry_after_seconds` rather
        than being trusted verbatim — the real ceiling enforcement still
        happens in `get()` via `max_retry_after_seconds` regardless of
        which branch below produced the number.
        """
        header_value = response.headers.get("Retry-After")
        if header_value is None:
            return self._default_retry_after_seconds

        stripped = header_value.strip()
        if stripped.isdigit():
            return max(0.0, float(stripped))

        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError):
            return self._default_retry_after_seconds
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        delta = (retry_at - datetime.now(UTC)).total_seconds()
        return max(0.0, delta)

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
