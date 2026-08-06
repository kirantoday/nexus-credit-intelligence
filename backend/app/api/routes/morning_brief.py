"""Morning Research Brief summary API route (PLAN.md 24.8, 24.9).

Not nested under `/filing-monitor` — the brief itself is meant to outlive
SEC being the only evidence contributor (PLAN.md 24.9). Thin per PLAN.md
section 3: delegates to `filing_monitor_api_service`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.filing_monitor import MorningBriefSummary
from app.services import filing_monitor_api_service

router = APIRouter(prefix="/api/morning-brief", tags=["morning-brief"])


@router.get("", response_model=MorningBriefSummary)
def get_morning_brief(db: Annotated[Session, Depends(get_db)]) -> MorningBriefSummary:
    return filing_monitor_api_service.get_morning_brief(db)
