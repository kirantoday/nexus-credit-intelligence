"""Overnight Distress Filing Monitor — run/filing API routes (PLAN.md 24.5, 24.8).

Thin per PLAN.md section 3: delegates to `filing_monitor_api_service`. The
manual-trigger endpoint is admin/demo-only — gated to non-production
environments as the interim stand-in for real role-based access control
until Milestone 9's user/role model exists (TD-002).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.factory import LLMConfigurationError, build_model_router
from app.config import get_settings
from app.core.types import FilingMonitorRunMode
from app.db.session import get_db
from app.schemas.filing_monitor import (
    FilingMonitorRunRow,
    FilingMonitorRunsPage,
    SecFilingsResponse,
)
from app.services import filing_monitor_api_service

router = APIRouter(prefix="/api/filing-monitor", tags=["filing-monitor"])


@router.get("/runs", response_model=FilingMonitorRunsPage)
def list_runs(
    db: Annotated[Session, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
) -> FilingMonitorRunsPage:
    runs = filing_monitor_api_service.list_runs(db, page=page, page_size=page_size)
    return FilingMonitorRunsPage(runs=runs)


@router.get("/runs/latest-successful", response_model=FilingMonitorRunRow)
def get_latest_successful_run(db: Annotated[Session, Depends(get_db)]) -> FilingMonitorRunRow:
    run = filing_monitor_api_service.get_latest_successful_run(db)
    if run is None:
        raise HTTPException(status_code=404, detail="No successful monitor run yet")
    return run


@router.get("/filings", response_model=SecFilingsResponse)
def list_new_filings(
    db: Annotated[Session, Depends(get_db)],
    since_run_id: UUID | None = None,
) -> SecFilingsResponse:
    return filing_monitor_api_service.list_new_filings(db, since_run_id=since_run_id)


@router.post("/runs/trigger", response_model=FilingMonitorRunRow)
def trigger_manual_run(
    db: Annotated[Session, Depends(get_db)],
    mode: Annotated[FilingMonitorRunMode, Body()],
    backfill_days: Annotated[int | None, Body()] = None,
) -> FilingMonitorRunRow:
    settings = get_settings()
    if settings.environment == "production":
        raise HTTPException(
            status_code=403,
            detail="Manual monitor runs are admin/demo-only and disabled in production "
            "until real role-based access control exists (TD-002).",
        )
    if not settings.sec_user_agent:
        raise HTTPException(status_code=503, detail="SEC_USER_AGENT is not configured")
    if mode is FilingMonitorRunMode.BACKFILL and not backfill_days:
        raise HTTPException(
            status_code=422, detail="backfill_days is required when mode is backfill"
        )

    try:
        router = build_model_router(settings)
    except LLMConfigurationError:
        router = None

    return filing_monitor_api_service.trigger_manual_run(
        db,
        mode=mode,
        backfill_days=backfill_days,
        environment=settings.environment,
        sec_user_agent=settings.sec_user_agent,
        router=router,
    )
