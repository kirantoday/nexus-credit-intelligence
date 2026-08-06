"""Credit Universe API route (PLAN.md section 5).

Thin per PLAN.md section 3: parses/validates the request, delegates to
`credit_universe_service`, returns its response — no business logic, no ORM
access here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.types import InstrumentType
from app.db.session import get_db
from app.repositories.security_repository import SortDirection, SortField
from app.schemas.credit_universe import CreditUniversePage
from app.services import credit_universe_service

router = APIRouter(prefix="/api/credit-universe", tags=["credit-universe"])


@router.get("", response_model=CreditUniversePage)
def get_credit_universe(
    db: Annotated[Session, Depends(get_db)],
    instrument_type: InstrumentType | None = None,
    is_synthetic: bool | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    sort_by: SortField = "legal_name",
    sort_dir: SortDirection = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> CreditUniversePage:
    return credit_universe_service.get_credit_universe_page(
        db,
        instrument_type=instrument_type,
        is_synthetic=is_synthetic,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )
