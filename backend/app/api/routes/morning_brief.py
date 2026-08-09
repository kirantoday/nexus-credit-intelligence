"""Morning Research Brief summary API route (PLAN.md 24.8, 24.9, Milestone
7.5.2 correction).

Not nested under `/filing-monitor` — the brief itself is meant to outlive
SEC being the only evidence contributor (PLAN.md 24.9). Thin per PLAN.md
section 3: delegates to `morning_brief_service`.

`GET` is a pure read (no side effects — safe to call repeatedly). `POST
/view` records that the brief was viewed, advancing the boundary for next
time; the frontend calls it only *after* `GET` has already resolved, so a
visit never reads its own not-yet-recorded view as its own boundary.
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


@router.post("/view", status_code=204, response_model=None)
def record_brief_view(db: Annotated[Session, Depends(get_db)]) -> None:
    morning_brief_service.record_brief_view(db)
