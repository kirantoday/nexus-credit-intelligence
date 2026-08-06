"""Response schema for the Market Context API.

Answers "what macroeconomic environment surrounds this credit?" (PLAN.md
section 18 step 5) directly and honestly: each field is a real FRED
observation shown as-is, with its own provenance/as-of date/freshness. No
blended or derived macro score — that's an explicit non-goal for this
milestone (see `services/market_context_service.py`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.freshness import FreshnessTier
from app.core.types import ProviderName


class MarketContextObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    series_id: str
    title: str
    value: Decimal
    units: str
    as_of_date: date
    freshness: FreshnessTier
    provider: ProviderName


class MarketContext(BaseModel):
    """`None` for a field whenever that series hasn't been synced yet —
    never a fabricated placeholder value."""

    model_config = ConfigDict(frozen=True)

    sofr: MarketContextObservation | None
    high_yield_oas: MarketContextObservation | None
