"""Issuer Distress Timeline API route (PLAN.md Milestone 7.5.4).

Thin per PLAN.md section 3: delegates to `issuer_timeline_service`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.issuer_timeline import IssuerTimeline
from app.services import issuer_timeline_service

router = APIRouter(prefix="/api/issuers", tags=["issuer-timeline"])


@router.get("/{issuer_id}/timeline", response_model=IssuerTimeline)
def get_issuer_timeline(issuer_id: UUID, db: Annotated[Session, Depends(get_db)]) -> IssuerTimeline:
    result = issuer_timeline_service.get_issuer_timeline(db, issuer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Issuer not found")
    return result
