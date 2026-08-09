"""Morning Research Brief summary API route (PLAN.md 24.8, 24.9, Milestone
7.5.2 correction).

Not nested under `/filing-monitor` — the brief itself is meant to outlive
SEC being the only evidence contributor (PLAN.md 24.9). Thin per PLAN.md
section 3: delegates to `morning_brief_service`.

A pure read, no side effects — safe to call any number of times without
changing the comparison window it returns (PLAN.md Milestone 7.5.2's
business-day-cycle correction: the window is derived from canonical run
data and calendar arithmetic, never from page-view state, so there is
nothing here for repeated requests to advance). The prior `POST /view`
endpoint (recording a page view to drive the boundary) was removed along
with the `morning_brief_view` table it wrote to — see PLAN.md TD-018/
TD-019 and `alembic/versions/0013_drop_morning_brief_view.py`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.morning_brief import MorningBriefSummary
from app.services import morning_brief_service

router = APIRouter(prefix="/api/morning-brief", tags=["morning-brief"])


@router.get("", response_model=MorningBriefSummary)
def get_morning_brief(db: Annotated[Session, Depends(get_db)]) -> MorningBriefSummary:
    return morning_brief_service.get_morning_brief(db)
