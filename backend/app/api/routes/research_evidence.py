"""Research Evidence API route (PLAN.md 24.3, 24.8) — provider-agnostic,
not filing-specific (ADR-018).

Thin per PLAN.md section 3: delegates to `filing_monitor_api_service`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.types import EvidenceSeverity, EvidenceType, ReviewStatus
from app.db.session import get_db
from app.schemas.filing_monitor import ResearchEvidencePage
from app.services import filing_monitor_api_service

router = APIRouter(prefix="/api/research-evidence", tags=["research-evidence"])


@router.get("", response_model=ResearchEvidencePage)
def list_research_evidence(
    db: Annotated[Session, Depends(get_db)],
    issuer_id: UUID | None = None,
    evidence_provider: str | None = None,
    evidence_type: EvidenceType | None = None,
    severity: EvidenceSeverity | None = None,
    review_status: ReviewStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ResearchEvidencePage:
    evidence = filing_monitor_api_service.list_evidence(
        db,
        issuer_id=issuer_id,
        evidence_provider=evidence_provider,
        evidence_type=evidence_type,
        severity=severity,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )
    return ResearchEvidencePage(evidence=evidence)
