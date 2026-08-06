"""Freshness: computed at read time, never persisted (PLAN.md section 16, ADR-005).

`freshness` (`live`/`cached`/`stale`) is derived from `provenance.retrieved_at`
plus a per-provider TTL policy, at the moment a value is displayed — never
stored, so it can never silently drift out of sync with "now." If a
historical snapshot is ever needed, it must be named `freshness_at_ingestion`
explicitly, never reusing this name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.core.types import ProviderName


class FreshnessTier(StrEnum):
    LIVE = "live"
    CACHED = "cached"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """How long a fetched value counts as `live`, and how long after that it
    counts as `cached` before becoming `stale`. Both are measured from
    `provenance.retrieved_at`, not from the underlying fact's `as_of_date`."""

    live_within: timedelta
    cached_within: timedelta


_DEFAULT_POLICY = FreshnessPolicy(live_within=timedelta(hours=1), cached_within=timedelta(hours=24))

_POLICIES: dict[ProviderName, FreshnessPolicy] = {
    # SEC filings/XBRL facts change on a filing cadence (quarterly/annual at
    # most), not intraday — a same-day fetch is "live," and it stays merely
    # "cached" (not stale) for a full week before a re-fetch is warranted.
    ProviderName.SEC_EDGAR: FreshnessPolicy(
        live_within=timedelta(hours=24), cached_within=timedelta(days=7)
    ),
    # TRACE trade prints are intraday market data.
    ProviderName.FINRA_TRACE: FreshnessPolicy(
        live_within=timedelta(minutes=15), cached_within=timedelta(hours=4)
    ),
    # FRED macro series publish on their own (often monthly) cadence.
    ProviderName.FRED: FreshnessPolicy(
        live_within=timedelta(days=1), cached_within=timedelta(days=30)
    ),
    # Synthetic demo data isn't fetched from anywhere real-time; it's never
    # stale on its own terms — a demo issuer's numbers don't age.
    ProviderName.SYNTHETIC: FreshnessPolicy(
        live_within=timedelta(days=36500), cached_within=timedelta(days=36500)
    ),
    # OpenFIGI identifier/reference data (FIGI, maturity, coupon on a bond
    # issue) doesn't change once assigned/issued — far slower-moving than
    # even SEC filings.
    ProviderName.OPENFIGI: FreshnessPolicy(
        live_within=timedelta(days=30), cached_within=timedelta(days=180)
    ),
}


def compute_freshness(
    retrieved_at: datetime, provider: ProviderName, *, now: datetime | None = None
) -> FreshnessTier:
    """The freshness tier for a value fetched at `retrieved_at` from `provider`, as of `now`."""
    policy = _POLICIES.get(provider, _DEFAULT_POLICY)
    current = now or datetime.now(UTC)
    age = current - retrieved_at
    if age <= policy.live_within:
        return FreshnessTier.LIVE
    if age <= policy.cached_within:
        return FreshnessTier.CACHED
    return FreshnessTier.STALE
