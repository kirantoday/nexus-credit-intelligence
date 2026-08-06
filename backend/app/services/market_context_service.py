"""Assembles the Market Context API response from FRED registry/observation data.

Cross-repository orchestration lives here, not in the route (kept thin per
PLAN.md section 3) or the repository (single-table concern) — PLAN.md section
17's `services/` layer.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.freshness import compute_freshness
from app.core.types import ProviderName
from app.repositories import fred_repository
from app.schemas.market_context import MarketContext, MarketContextObservation

# The two series Milestone 5 syncs (PLAN.md section 18 step 5) — SOFR because
# it's the floating-rate benchmark this platform's loan securities actually
# reference, HY OAS because it's the credit market's own backdrop indicator,
# directly relevant to a distressed-credit/leveraged-finance audience.
_SOFR_SERIES_ID = "SOFR"
_HY_OAS_SERIES_ID = "BAMLH0A0HYM2"


def _build_observation(db: Session, series_id: str) -> MarketContextObservation | None:
    series = fred_repository.get_series(db, series_id)
    observation = fred_repository.get_latest_observation(db, series_id)
    if series is None or observation is None:
        return None
    return MarketContextObservation(
        series_id=series_id,
        title=series.title,
        value=observation.value,
        units=series.units,
        as_of_date=observation.obs_date,
        # `series.last_synced_at` stands in for this observation's own
        # `retrieved_at` (they're set from the same sync run's timestamp,
        # `providers/fred/provider.py`'s `sync_series`) — avoids a second
        # lookup through `provenance_id` just for a freshness computation.
        freshness=compute_freshness(series.last_synced_at, ProviderName.FRED),
        provider=ProviderName.FRED,
    )


def get_market_context(db: Session) -> MarketContext:
    return MarketContext(
        sofr=_build_observation(db, _SOFR_SERIES_ID),
        high_yield_oas=_build_observation(db, _HY_OAS_SERIES_ID),
    )
