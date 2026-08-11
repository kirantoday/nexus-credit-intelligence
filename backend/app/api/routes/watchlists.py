"""Watchlists API routes (PLAN.md section 24.1; Milestone 8).

Thin per PLAN.md section 3: delegates to `watchlist_service`, no business
logic or ORM access here.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.watchlist import (
    AddIssuerToWatchlistRequest,
    WatchlistCreateRequest,
    WatchlistDetailResponse,
    WatchlistListResponse,
    WatchlistSummary,
    WatchlistUpdateRequest,
)
from app.services import watchlist_service

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


@router.get("", response_model=WatchlistListResponse)
def list_watchlists(
    db: Annotated[Session, Depends(get_db)],
    issuer_id: UUID | None = None,
) -> WatchlistListResponse:
    watchlists = watchlist_service.list_watchlists(db, issuer_id=issuer_id)
    return WatchlistListResponse(watchlists=watchlists)


@router.post("", response_model=WatchlistSummary, status_code=status.HTTP_201_CREATED)
def create_watchlist(
    body: WatchlistCreateRequest, db: Annotated[Session, Depends(get_db)]
) -> WatchlistSummary:
    return watchlist_service.create_watchlist(db, name=body.name, description=body.description)


@router.get("/{watchlist_id}", response_model=WatchlistDetailResponse)
def get_watchlist(
    watchlist_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> WatchlistDetailResponse:
    result = watchlist_service.get_watchlist_detail(db, watchlist_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return result


@router.patch("/{watchlist_id}", response_model=WatchlistSummary)
def update_watchlist(
    watchlist_id: UUID, body: WatchlistUpdateRequest, db: Annotated[Session, Depends(get_db)]
) -> WatchlistSummary:
    result = watchlist_service.update_watchlist(
        db, watchlist_id, name=body.name, description=body.description
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return result


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_watchlist(watchlist_id: UUID, db: Annotated[Session, Depends(get_db)]) -> None:
    deleted = watchlist_service.delete_watchlist(db, watchlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist not found")


@router.post("/{watchlist_id}/issuers", response_model=WatchlistSummary)
def add_issuer(
    watchlist_id: UUID,
    body: AddIssuerToWatchlistRequest,
    db: Annotated[Session, Depends(get_db)],
) -> WatchlistSummary:
    """Idempotent: adding an issuer already on the Watchlist is a no-op
    success (200), never a duplicate-membership error — the "already added"
    state is something the Add to Watchlist UI shows, not something the API
    rejects."""
    result = watchlist_service.add_issuer(
        db, watchlist_id, issuer_id=body.issuer_id, rationale=body.rationale
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Watchlist or issuer not found")
    summary, _created = result
    return summary


@router.delete(
    "/{watchlist_id}/issuers/{issuer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_issuer(
    watchlist_id: UUID, issuer_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> None:
    removed = watchlist_service.remove_issuer(db, watchlist_id, issuer_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Watchlist or membership not found")
