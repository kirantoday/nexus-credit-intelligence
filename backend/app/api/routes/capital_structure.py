"""Capital Structure API route (PLAN.md section 7).

Thin per PLAN.md section 3: delegates to `capital_structure_service`, no
business logic or ORM access here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.capital_structure import CapitalStructureResponse
from app.services import capital_structure_service

router = APIRouter(prefix="/api/issuers", tags=["capital-structure"])


@router.get("/{issuer_id}/capital-structure", response_model=CapitalStructureResponse)
def get_capital_structure(
    issuer_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> CapitalStructureResponse:
    result = capital_structure_service.get_capital_structure(db, issuer_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Issuer not found")
    return result
