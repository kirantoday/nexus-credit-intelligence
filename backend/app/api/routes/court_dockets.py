"""Court Docket API routes (PLAN.md sections 4.5, 15, Milestone 7).

Thin per PLAN.md section 3: delegates to `court_docket_api_service`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.court_docket import CourtDocketDetail, CourtDocketsResponse
from app.services import court_docket_api_service

router = APIRouter(prefix="/api/court-dockets", tags=["court-dockets"])


@router.get("", response_model=CourtDocketsResponse)
def list_court_dockets(
    db: Annotated[Session, Depends(get_db)], issuer_id: UUID | None = None
) -> CourtDocketsResponse:
    return court_docket_api_service.list_dockets(db, issuer_id=issuer_id)


@router.get("/{docket_id}", response_model=CourtDocketDetail)
def get_court_docket(db: Annotated[Session, Depends(get_db)], docket_id: UUID) -> CourtDocketDetail:
    detail = court_docket_api_service.get_docket_detail(db, docket_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Court docket not found")
    return detail
