"""CourtListener REST API v4 HTTP client (PLAN.md sections 4.5, 15, Milestone 7).

Two real, live-verified access tiers (confirmed during Milestone 7
development, not assumed from documentation alone): the Search API
(`/api/rest/v4/search/?type=r`) is open anonymously; the PACER-derived
Docket/DocketEntry/RECAPDocument detail endpoints require a real
`Authorization: Token ...` header (401 otherwise). This client always sends
the token when configured (`COURTLISTENER_API_TOKEN`) so both tiers work;
docket-entry sync is simply unavailable without one (see
`app.ai.factory`-style "the app stays operational without a key" pattern —
`app.services.court_docket_service` documents its own behavior when no
token is configured).

Never calls the RECAP "fetch" (PACER-purchase) or upload endpoints — this
client is read-only against material CourtListener has already scraped and
made available (PLAN.md section 22: never perform a real PACER purchase in
this build).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar
from urllib.parse import quote

from app.providers.base.http_client import ThrottledHttpClient
from app.providers.courtlistener.dto import (
    CourtListenerSearchResponseDTO,
    DocketEntriesPageDTO,
)

_BASE_URL = "https://www.courtlistener.com"
_SEARCH_URL = f"{_BASE_URL}/api/rest/v4/search/"
_DOCKET_ENTRIES_URL = f"{_BASE_URL}/api/rest/v4/docket-entries/"

# CourtListener's real, live-observed authenticated throttle is 10/min
# (confirmed via a genuine 429 during development: "Rate limit exceeded:
# 10/min"). 7 seconds between requests keeps this client comfortably under
# that even with the fixed per-request overhead of pagination.
COURTLISTENER_MIN_INTERVAL_SECONDS = 7.0

_DtoT = TypeVar("_DtoT")


@dataclass(frozen=True, slots=True)
class FetchResult(Generic[_DtoT]):
    dto: _DtoT
    raw_bytes: bytes
    content_type: str
    url: str
    retrieved_at: datetime


def build_http_client(
    *, user_agent: str, api_token: str | None, max_retry_after_seconds: float = 60.0
) -> ThrottledHttpClient:
    """The one place Authorization/throttle/retry configuration for
    CourtListener is assembled, so every caller (the live service, the seed
    script, tests) gets identical, real behavior.

    `timeout_seconds=120.0` — live-observed real need: `ThrottledHttpClient`'s
    30s default was too short for a page request retried after a 429
    backoff, causing a genuine `ReadTimeout` mid-sync of a large real docket
    (see BUILD_LOG.md). An isolated diagnostic call confirmed CourtListener
    itself, not a bug here, is the source of the delay: a single page fetch
    legitimately took 66.7 real seconds to respond. 120s leaves headroom
    above that observed real-world latency. A large Chapter 11 case's
    docket can run to hundreds of entries across many paginated requests,
    so a full sync is expected to take a genuinely long time today, not to
    hang indefinitely.

    `max_retry_after_seconds` (default matches `Settings.courtlistener_retry_after_max_seconds`
    — callers with a live `Settings` instance should pass that explicitly,
    this default only covers callers that don't): PLAN.md Milestone 7.5.3's
    live-caught defect — a single `Retry-After`-driven wait blocked an
    entire discovery batch for 4+ hours because nothing capped it. Beyond
    this ceiling, `ThrottledHttpClient.get` raises `RetryAfterTooLongError`
    instead of sleeping, which this codebase's existing per-issuer/
    per-provider isolation (`enrichment_orchestrator.enrich_issuer`)
    already turns into a `FAILED_RETRYABLE` status with a `next_retry_at`
    — CourtListener stalling never blocks the rest of a discovery run.
    """
    extra_headers = {"Authorization": f"Token {api_token}"} if api_token else None
    return ThrottledHttpClient(
        user_agent=user_agent,
        min_interval_seconds=COURTLISTENER_MIN_INTERVAL_SECONDS,
        timeout_seconds=120.0,
        extra_headers=extra_headers,
        retry_on_status=frozenset({429}),
        max_retries=2,
        max_retry_after_seconds=max_retry_after_seconds,
    )


class CourtListenerClient:
    def __init__(self, http_client: ThrottledHttpClient) -> None:
        self._http = http_client

    def search_dockets(
        self, query: str, *, court: str | None = None
    ) -> FetchResult[CourtListenerSearchResponseDTO]:
        """RECAP docket search (`type=r`) — works anonymously, but this
        client always sends the token when configured. Free-text `query`
        (typically an issuer's legal name); `court` narrows to a specific
        CourtListener court id (e.g. `deb` for D. Del. Bankruptcy, `txsb`
        for S.D. Tex. Bankruptcy)."""
        params = f"type=r&q={_url_quote(query)}"
        if court:
            params += f"&court={_url_quote(court)}"
        url = f"{_SEARCH_URL}?{params}"
        response = self._http.get(url)
        retrieved_at = datetime.now(UTC)
        dto = CourtListenerSearchResponseDTO.model_validate(json.loads(response.raw_bytes))
        return FetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            url=url,
            retrieved_at=retrieved_at,
        )

    def fetch_docket_entries_page(self, url: str) -> FetchResult[DocketEntriesPageDTO]:
        """Fetches one page of docket entries. `url` is either the initial
        constructed URL (see `docket_entries_url`) or a `next` page URL
        CourtListener itself returned — never hand-constructed for page 2+,
        since CourtListener's own pagination cursor is the only reliable
        source of it."""
        response = self._http.get(url)
        retrieved_at = datetime.now(UTC)
        dto = DocketEntriesPageDTO.model_validate(json.loads(response.raw_bytes))
        return FetchResult(
            dto=dto,
            raw_bytes=response.raw_bytes,
            content_type=response.content_type,
            url=url,
            retrieved_at=retrieved_at,
        )

    def docket_entries_url(self, courtlistener_docket_id: int) -> str:
        return f"{_DOCKET_ENTRIES_URL}?docket={courtlistener_docket_id}&order_by=entry_number"

    def docket_entries_incremental_url(
        self, courtlistener_docket_id: int, *, since_entry_id: int
    ) -> str:
        """TD-012 incremental sync (PLAN.md Milestone 7.5): only entries
        with `id` strictly greater than the highest `courtlistener_entry_id`
        already synced for this docket — `id` is CourtListener's own
        globally monotonic identifier (live-verified via `OPTIONS`), so this
        never re-fetches an already-synced entry and never needs an overlap
        margin the way a timestamp-based cursor would."""
        return (
            f"{_DOCKET_ENTRIES_URL}?docket={courtlistener_docket_id}"
            f"&id__gt={since_entry_id}&order_by=id"
        )


def absolute_courtlistener_url(path_or_url: str | None) -> str | None:
    """CourtListener's `*_absolute_url` fields are site-relative paths
    (e.g. `/docket/67460054/...`), not full URLs — this is the one place
    that gets resolved into a real, clickable `source_url`."""
    if path_or_url is None:
        return None
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    return f"{_BASE_URL}{path_or_url}"


def _url_quote(value: str) -> str:
    return quote(value, safe="")
