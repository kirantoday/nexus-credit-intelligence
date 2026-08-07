"""Repository for `research_evidence` (PLAN.md section 24.3, ADR-018).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
Filters are provider-agnostic, not filing-specific — `evidence_provider` is
just another filter value, not a special case.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import DetectionMethod, EvidenceSeverity, EvidenceType, ReviewStatus
from app.domain.research_evidence import ResearchEvidence, ResearchEvidenceCreate
from app.models.research_evidence import ResearchEvidence as ResearchEvidenceModel


def _to_domain(row: ResearchEvidenceModel) -> ResearchEvidence:
    return ResearchEvidence(
        id=row.id,
        issuer_id=row.issuer_id,
        evidence_provider=row.evidence_provider,
        source_type=row.source_type,
        filing_id=row.filing_id,
        docket_entry_id=row.docket_entry_id,
        evidence_type=EvidenceType(row.evidence_type),
        severity=EvidenceSeverity(row.severity),
        source_section=row.source_section,
        source_item=row.source_item,
        matched_rule=row.matched_rule,
        evidence_excerpt=row.evidence_excerpt,
        evidence_start_offset=row.evidence_start_offset,
        evidence_end_offset=row.evidence_end_offset,
        confidence=float(row.confidence) if row.confidence is not None else None,
        detection_method=DetectionMethod(row.detection_method),
        provenance_id=row.provenance_id,
        created_at=row.created_at,
        review_status=ReviewStatus(row.review_status),
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
    )


def create_evidence(db: Session, data: ResearchEvidenceCreate) -> ResearchEvidence:
    row = ResearchEvidenceModel(
        issuer_id=data.issuer_id,
        evidence_provider=data.evidence_provider,
        source_type=data.source_type,
        filing_id=data.filing_id,
        docket_entry_id=data.docket_entry_id,
        evidence_type=data.evidence_type.value,
        severity=data.severity.value,
        source_section=data.source_section,
        source_item=data.source_item,
        matched_rule=data.matched_rule,
        evidence_excerpt=data.evidence_excerpt,
        evidence_start_offset=data.evidence_start_offset,
        evidence_end_offset=data.evidence_end_offset,
        confidence=data.confidence,
        detection_method=data.detection_method.value,
        provenance_id=data.provenance_id,
        review_status=data.review_status.value,
        reviewed_by=data.reviewed_by,
        reviewed_at=data.reviewed_at,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_evidence(db: Session, evidence_id: UUID) -> ResearchEvidence | None:
    row = db.get(ResearchEvidenceModel, evidence_id)
    return _to_domain(row) if row is not None else None


def list_evidence_by_filing(db: Session, filing_id: UUID) -> list[ResearchEvidence]:
    stmt = select(ResearchEvidenceModel).where(ResearchEvidenceModel.filing_id == filing_id)
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def list_evidence_by_docket_entry(db: Session, docket_entry_id: UUID) -> list[ResearchEvidence]:
    stmt = select(ResearchEvidenceModel).where(
        ResearchEvidenceModel.docket_entry_id == docket_entry_id
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def list_evidence_by_ids(db: Session, evidence_ids: list[UUID]) -> list[ResearchEvidence]:
    if not evidence_ids:
        return []
    stmt = select(ResearchEvidenceModel).where(ResearchEvidenceModel.id.in_(evidence_ids))
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def list_evidence(
    db: Session,
    *,
    issuer_id: UUID | None = None,
    evidence_provider: str | None = None,
    evidence_type: EvidenceType | None = None,
    severity: EvidenceSeverity | None = None,
    review_status: ReviewStatus | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[ResearchEvidence]:
    stmt = select(ResearchEvidenceModel)
    if issuer_id is not None:
        stmt = stmt.where(ResearchEvidenceModel.issuer_id == issuer_id)
    if evidence_provider is not None:
        stmt = stmt.where(ResearchEvidenceModel.evidence_provider == evidence_provider)
    if evidence_type is not None:
        stmt = stmt.where(ResearchEvidenceModel.evidence_type == evidence_type.value)
    if severity is not None:
        stmt = stmt.where(ResearchEvidenceModel.severity == severity.value)
    if review_status is not None:
        stmt = stmt.where(ResearchEvidenceModel.review_status == review_status.value)
    stmt = (
        stmt.order_by(ResearchEvidenceModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]


def count_evidence_created_since(db: Session, since: datetime | None) -> int:
    """Provider-agnostic count by `created_at` — backs the Morning Research
    Brief's "New Research Evidence" metric across every evidence provider
    (SEC, CourtListener, and future ones), not just SEC filings."""
    stmt = select(func.count()).select_from(ResearchEvidenceModel)
    if since is not None:
        stmt = stmt.where(ResearchEvidenceModel.created_at >= since)
    return db.execute(stmt).scalar_one()
