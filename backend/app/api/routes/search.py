"""Universal Search API routes (PLAN.md 4.13, 8; Milestone 12A).

Thin per PLAN.md section 3: delegates to `search_service`, no business
logic or ORM access here. One endpoint, reused by both the header
typeahead (`limit=5`) and the `/search` page (`limit=10`) — deliberately
no pagination inside this endpoint; "see all results" reuses each
entity's own existing, already-paginated list page.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.search import SearchResponse
from app.services import search_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=0, max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=25)] = 5,
) -> SearchResponse:
    return search_service.search(db, q, per_group_limit=limit)
