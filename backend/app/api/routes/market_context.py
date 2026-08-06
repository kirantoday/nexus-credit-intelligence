"""Market Context API route (PLAN.md section 18 step 5).

Thin per PLAN.md section 3: delegates to `market_context_service`, no
business logic or ORM access here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.market_context import MarketContext
from app.services import market_context_service

router = APIRouter(prefix="/api/market-context", tags=["market-context"])


@router.get("", response_model=MarketContext)
def get_market_context(db: Annotated[Session, Depends(get_db)]) -> MarketContext:
    return market_context_service.get_market_context(db)
