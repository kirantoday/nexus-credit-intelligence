"""Integration tests for market_context_service against the live nexus schema.

Reads the real SOFR/HY OAS data Milestone 5's seed script permanently
committed (see BUILD_LOG.md) — there is nothing to seed here, this proves
the assembled API response is correct against genuinely live-synced data.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.freshness import FreshnessTier
from app.core.types import ProviderName
from app.services import market_context_service


def test_get_market_context_returns_real_sofr(db_session: Session) -> None:
    context = market_context_service.get_market_context(db_session)

    assert context.sofr is not None
    assert context.sofr.series_id == "SOFR"
    assert context.sofr.title == "Secured Overnight Financing Rate"
    assert context.sofr.value > Decimal(0)
    assert context.sofr.value < Decimal(100)
    assert context.sofr.provider is ProviderName.FRED
    assert context.sofr.freshness in (FreshnessTier.LIVE, FreshnessTier.CACHED)


def test_get_market_context_returns_real_high_yield_oas(db_session: Session) -> None:
    context = market_context_service.get_market_context(db_session)

    assert context.high_yield_oas is not None
    assert context.high_yield_oas.series_id == "BAMLH0A0HYM2"
    assert context.high_yield_oas.value > Decimal(0)
    assert context.high_yield_oas.provider is ProviderName.FRED
