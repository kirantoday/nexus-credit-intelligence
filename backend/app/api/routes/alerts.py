"""Alerts API routes (PLAN.md 24.3, 24.8) — provider-agnostic, not
filing-specific (ADR-018).

Thin per PLAN.md section 3: delegates to `filing_monitor_api_service`.
Acknowledge/dismiss both accept an optional `acted_by` — free text, no FK
(no `user` table yet, matching this codebase's existing "auth disabled,
implicit admin" posture, TD-002).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.types import AlertStatus, DetectionMethod, EvidenceSeverity
from app.db.session import get_db
from app.schemas.filing_monitor import AlertEvidenceDetail, AlertRow, AlertsPage
from app.services import filing_monitor_api_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertsPage)
def list_alerts(
    db: Annotated[Session, Depends(get_db)],
    issuer_id: UUID | None = None,
    universe_id: UUID | None = None,
    severity: EvidenceSeverity | None = None,
    category: str | None = None,
    evidence_provider: str | None = None,
    status: AlertStatus | None = None,
    detection_method: DetectionMethod | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AlertsPage:
    return filing_monitor_api_service.list_alerts(
        db,
        issuer_id=issuer_id,
        universe_id=universe_id,
        severity=severity,
        category=category,
        evidence_provider=evidence_provider,
        status=status,
        detection_method=detection_method,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.get("/{alert_id}/evidence", response_model=AlertEvidenceDetail)
def get_alert_evidence(
    alert_id: UUID, db: Annotated[Session, Depends(get_db)]
) -> AlertEvidenceDetail:
    result = filing_monitor_api_service.get_alert_evidence_detail(db, alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.post("/{alert_id}/acknowledge", response_model=AlertRow)
def acknowledge_alert(
    alert_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    acted_by: Annotated[str | None, Body()] = None,
) -> AlertRow:
    try:
        return filing_monitor_api_service.acknowledge_alert(db, alert_id, acknowledged_by=acted_by)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{alert_id}/dismiss", response_model=AlertRow)
def dismiss_alert(
    alert_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    acted_by: Annotated[str | None, Body()] = None,
    reason: Annotated[str | None, Body()] = None,
) -> AlertRow:
    try:
        return filing_monitor_api_service.dismiss_alert(
            db, alert_id, dismissed_by=acted_by, dismissal_reason=reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
