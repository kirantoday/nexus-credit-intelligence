"""Research Universes API routes (PLAN.md section 24.1, 24.8).

Thin per PLAN.md section 3: delegates to `research_universe_service`, no
business logic or ORM access here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.types import CollectionType
from app.db.session import get_db
from app.schemas.research_universe import (
    ResearchUniverseIssuersResponse,
    ResearchUniverseListResponse,
    ResearchUniverseSummary,
)
from app.services import research_universe_service

router = APIRouter(prefix="/api/research-universes", tags=["research-universes"])


@router.get("", response_model=ResearchUniverseListResponse)
def list_research_universes(
    db: Annotated[Session, Depends(get_db)],
    collection_type: CollectionType | None = None,
) -> ResearchUniverseListResponse:
    universes = research_universe_service.list_research_universes(
        db, collection_type=collection_type
    )
    return ResearchUniverseListResponse(universes=universes)


@router.get("/{universe_id}", response_model=ResearchUniverseSummary)
def get_research_universe(
    universe_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> ResearchUniverseSummary:
    result = research_universe_service.get_research_universe(db, universe_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Research universe not found")
    return result


@router.get("/{universe_id}/issuers", response_model=ResearchUniverseIssuersResponse)
def get_research_universe_issuers(
    universe_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> ResearchUniverseIssuersResponse:
    result = research_universe_service.get_research_universe_issuers(db, universe_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Research universe not found")
    return result
