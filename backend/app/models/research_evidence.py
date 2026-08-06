"""ORM model for `research_evidence` (PLAN.md section 24.3, ADR-018).

Generalized — **not** `distress_evidence`. Represents any research signal,
not only SEC-filing-derived distress signals: `evidence_provider` names which
provider produced it (`sec_edgar` today; CourtListener/FRED/ratings/macro
providers add their own value later without a table rename). `filing_id` is
this milestone's one concrete, FK-enforced source pointer — future providers
add their own nullable source-specific FK the same way (TD-007/ADR-015
precedent), rather than a premature polymorphic association.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import DetectionMethod, EvidenceSeverity, EvidenceType, ReviewStatus
from app.db.base import Base

_EVIDENCE_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in EvidenceType)
_SEVERITY_SQL_LIST = ", ".join(f"'{value}'" for value in EvidenceSeverity)
_DETECTION_METHOD_SQL_LIST = ", ".join(f"'{value}'" for value in DetectionMethod)
_REVIEW_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in ReviewStatus)


class ResearchEvidence(Base):
    __tablename__ = "research_evidence"
    __table_args__ = (
        CheckConstraint(
            f"evidence_type IN ({_EVIDENCE_TYPE_SQL_LIST})", name="ck_research_evidence_type"
        ),
        CheckConstraint(
            f"severity IN ({_SEVERITY_SQL_LIST})", name="ck_research_evidence_severity"
        ),
        CheckConstraint(
            f"detection_method IN ({_DETECTION_METHOD_SQL_LIST})",
            name="ck_research_evidence_detection_method",
        ),
        CheckConstraint(
            f"review_status IN ({_REVIEW_STATUS_SQL_LIST})",
            name="ck_research_evidence_review_status",
        ),
        Index("ix_research_evidence_issuer_id", "issuer_id"),
        Index("ix_research_evidence_filing_id", "filing_id"),
        Index("ix_research_evidence_provenance_id", "provenance_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    evidence_provider: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sec_filing.id"), nullable=True
    )
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    source_section: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_item: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_rule: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    detection_method: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    review_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'unreviewed'")
    )
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
