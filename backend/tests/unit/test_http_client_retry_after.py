"""Unit tests for `ThrottledHttpClient`'s Retry-After handling (PLAN.md
Milestone 7.5.3) — the live-caught defect where a single retry wait
stalled an entire discovery batch for 4+ hours because nothing capped
`time.sleep()`. No network — `httpx.MockTransport` simulates every
response.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from app.providers.base.http_client import RetryAfterTooLongError, ThrottledHttpClient


def _client(**kwargs: object) -> ThrottledHttpClient:
    return ThrottledHttpClient(
        user_agent="test",
        retry_on_status=frozenset({429}),
        max_retries=2,
        max_retry_after_seconds=60.0,
        **kwargs,  # type: ignore[arg-type]
    )


def _response(headers: dict[str, str]) -> httpx.Response:
    return httpx.Response(429, headers=headers, request=httpx.Request("GET", "http://x"))


def test_normal_delta_seconds_parsed_correctly() -> None:
    client = _client()
    assert client._retry_after_seconds(_response({"Retry-After": "30"})) == 30.0


def test_malformed_value_falls_back_to_default() -> None:
    client = _client()
    assert client._retry_after_seconds(_response({"Retry-After": "not-a-number"})) == 15.0


def test_missing_header_falls_back_to_default() -> None:
    client = _client()
    assert client._retry_after_seconds(_response({})) == 15.0


def test_http_date_format_parsed_correctly() -> None:
    client = _client()
    future = datetime.now(UTC) + timedelta(seconds=45)
    header = format_datetime(future, usegmt=True)
    seconds = client._retry_after_seconds(_response({"Retry-After": header}))
    assert 40.0 < seconds <= 45.0


def test_past_http_date_clamped_to_zero_not_negative() -> None:
    client = _client()
    past = datetime.now(UTC) - timedelta(seconds=30)
    header = format_datetime(past, usegmt=True)
    assert client._retry_after_seconds(_response({"Retry-After": header})) == 0.0


def test_huge_delta_seconds_parsed_but_not_capped_at_this_layer() -> None:
    """`_retry_after_seconds` itself is a pure RFC 7231 parser — the huge
    value (a real-world mistaken-timestamp case) is parsed faithfully;
    `get()` is what enforces the ceiling, tested below."""
    client = _client()
    assert client._retry_after_seconds(_response({"Retry-After": "1754756230"})) == 1754756230.0


def test_get_raises_instead_of_sleeping_when_retry_after_exceeds_ceiling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "1754756230"})

    client = _client()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    started = time.monotonic()
    with pytest.raises(RetryAfterTooLongError):
        client.get("http://example.test/x")
    elapsed = time.monotonic() - started

    assert elapsed < 5.0, "must not sleep for anywhere near the requested duration"


def test_get_retries_normally_within_the_ceiling_then_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    client = _client()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    response = client.get("http://example.test/x")
    assert response.status_code == 200
    assert calls["count"] == 2


def test_repeated_429_exhausts_retries_and_raises_http_status_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"})

    client = _client()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        client.get("http://example.test/x")


def _client_with_transient_5xx_retry(**kwargs: object) -> ThrottledHttpClient:
    """Mirrors `run_market_discovery.py`'s SEC discovery client config
    (2026-08-12/13 incident: an unretried, transient `efts.sec.gov` 500
    aborted two consecutive production runs) — same generic retry
    mechanism `_client()` above already proves for 429, just against the
    transient-5xx set instead of a rate-limit status."""
    return ThrottledHttpClient(
        user_agent="test",
        retry_on_status=frozenset({500, 502, 503, 504}),
        max_retries=2,
        **kwargs,  # type: ignore[arg-type]
    )


def test_sec_500_is_retried_then_succeeds() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    client = _client_with_transient_5xx_retry()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    response = client.get("http://example.test/x")
    assert response.status_code == 200
    assert calls["count"] == 2


def test_sec_500_retry_exhaustion_still_surfaces_the_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client_with_transient_5xx_retry()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        client.get("http://example.test/x")


def test_non_retryable_status_is_unaffected_by_5xx_retry_config() -> None:
    """A status outside the configured `retry_on_status` set (e.g. a plain
    404) must still raise immediately, in a single call — enabling 5xx
    retry for transient SEC errors must not change behavior for genuinely
    non-retryable responses."""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404)

    client = _client_with_transient_5xx_retry()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        client.get("http://example.test/x")
    assert calls["count"] == 1


def test_default_client_still_raises_immediately_on_500_when_retry_not_configured() -> None:
    """Every existing caller that doesn't opt into `retry_on_status` (e.g.
    OpenFIGI/FRED, and SEC EDGAR's non-discovery call sites) must keep
    raising on the first non-2xx exactly as before — this fix is scoped to
    the discovery script's SEC client, not a global default change."""
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500)

    client = ThrottledHttpClient(user_agent="test")
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError):
        client.get("http://example.test/x")
    assert calls["count"] == 1
