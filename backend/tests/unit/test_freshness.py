"""Unit tests for app/core/freshness.py (PLAN.md section 16)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.freshness import FreshnessTier, compute_freshness
from app.core.types import ProviderName

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(minutes=1), FreshnessTier.LIVE),
        (timedelta(hours=23), FreshnessTier.LIVE),
        (timedelta(hours=24), FreshnessTier.LIVE),
        (timedelta(hours=25), FreshnessTier.CACHED),
        (timedelta(days=6), FreshnessTier.CACHED),
        (timedelta(days=7), FreshnessTier.CACHED),
        (timedelta(days=8), FreshnessTier.STALE),
        (timedelta(days=365), FreshnessTier.STALE),
    ],
)
def test_sec_edgar_policy_boundaries(age: timedelta, expected: FreshnessTier) -> None:
    retrieved_at = _NOW - age
    assert compute_freshness(retrieved_at, ProviderName.SEC_EDGAR, now=_NOW) is expected


def test_finra_trace_has_a_tighter_policy_than_sec_edgar() -> None:
    # 1 hour: still LIVE for SEC filings (24h live window), but past TRACE's
    # 15-minute live window (into TRACE's "cached" tier, not yet stale).
    one_hour_ago = _NOW - timedelta(hours=1)
    assert compute_freshness(one_hour_ago, ProviderName.SEC_EDGAR, now=_NOW) is FreshnessTier.LIVE
    assert (
        compute_freshness(one_hour_ago, ProviderName.FINRA_TRACE, now=_NOW) is FreshnessTier.CACHED
    )

    # 5 hours: past TRACE's 4-hour cached window entirely -> stale, while SEC
    # filings are still comfortably LIVE.
    five_hours_ago = _NOW - timedelta(hours=5)
    assert compute_freshness(five_hours_ago, ProviderName.SEC_EDGAR, now=_NOW) is FreshnessTier.LIVE
    assert (
        compute_freshness(five_hours_ago, ProviderName.FINRA_TRACE, now=_NOW) is FreshnessTier.STALE
    )


def test_synthetic_data_never_goes_stale() -> None:
    retrieved_at = _NOW - timedelta(days=3650)
    assert compute_freshness(retrieved_at, ProviderName.SYNTHETIC, now=_NOW) is FreshnessTier.LIVE


def test_openfigi_reference_data_has_a_long_lived_policy() -> None:
    # FIGI/maturity/coupon on a bond issue don't change once assigned —
    # still LIVE a week after retrieval, unlike SEC_EDGAR's 24h window.
    one_week_ago = _NOW - timedelta(days=7)
    assert compute_freshness(one_week_ago, ProviderName.OPENFIGI, now=_NOW) is FreshnessTier.LIVE
    assert compute_freshness(one_week_ago, ProviderName.SEC_EDGAR, now=_NOW) is FreshnessTier.CACHED


def test_unknown_provider_falls_back_to_default_policy() -> None:
    # ProviderName.COURTLISTENER has no explicit policy entry yet.
    retrieved_at = _NOW - timedelta(minutes=30)
    assert (
        compute_freshness(retrieved_at, ProviderName.COURTLISTENER, now=_NOW) is FreshnessTier.LIVE
    )
    retrieved_at_old = _NOW - timedelta(hours=2)
    assert (
        compute_freshness(retrieved_at_old, ProviderName.COURTLISTENER, now=_NOW)
        is FreshnessTier.CACHED
    )


def test_future_retrieved_at_is_treated_as_live() -> None:
    """Clock skew shouldn't produce a nonsensical 'stale' result for a value
    retrieved slightly in the future."""
    retrieved_at = _NOW + timedelta(minutes=5)
    assert compute_freshness(retrieved_at, ProviderName.SEC_EDGAR, now=_NOW) is FreshnessTier.LIVE


def test_defaults_to_real_now_when_not_provided() -> None:
    recent = datetime.now(UTC) - timedelta(seconds=1)
    assert compute_freshness(recent, ProviderName.SEC_EDGAR) is FreshnessTier.LIVE
