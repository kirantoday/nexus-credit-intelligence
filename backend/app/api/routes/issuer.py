"""Issuer Detail API route (Milestone 6).

Thin per PLAN.md section 3: delegates to `issuer_service`, no business logic
or ORM access here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.issuer import IssuerDetail
from app.services import issuer_service

router = APIRouter(prefix="/api/issuers", tags=["issuer"])


@router.get("/{issuer_id}", response_model=IssuerDetail)
def get_issuer(issuer_id: UUID, db: Annotated[Session, Depends(get_db)]) -> IssuerDetail:
    result = issuer_service.get_issuer_detail(db, issuer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Issuer not found")
    return result
