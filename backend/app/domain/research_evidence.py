"""Canonical domain object for `research_evidence` (PLAN.md section 24.3, ADR-018).

Generalized — **not** `distress_evidence`. `evidence_provider` names which
provider produced this evidence (`sec_edgar` today; future providers add
their own value, never a table rename). `filing_id` is this milestone's one
concrete source pointer; see the ORM model's docstring for why a polymorphic
association isn't built yet (TD-007/ADR-015 precedent).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import DetectionMethod, EvidenceSeverity, EvidenceType, ReviewStatus


class ResearchEvidenceCreate(BaseModel):
    """Everything needed to create a `research_evidence` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    evidence_provider: str
    source_type: str
    filing_id: UUID | None = None
    evidence_type: EvidenceType
    severity: EvidenceSeverity
    source_section: str | None = None
    source_item: str | None = None
    matched_rule: str
    evidence_excerpt: str
    evidence_start_offset: int | None = None
    evidence_end_offset: int | None = None
    confidence: float | None = None
    detection_method: DetectionMethod
    provenance_id: UUID
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None

    @model_validator(mode="after")
    def _excerpt_not_empty(self) -> ResearchEvidenceCreate:
        if not self.evidence_excerpt.strip():
            raise ValueError("evidence_excerpt must not be empty")
        return self


class ResearchEvidence(ResearchEvidenceCreate):
    """A persisted `research_evidence` row."""

    id: UUID
    created_at: datetime
