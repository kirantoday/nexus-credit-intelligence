"""ORM model for `market_discovery_candidate` (PLAN.md Milestone 7.5).

One row per unique `(cik, accession_no)` SEC full-text-search hit ever
examined. `(cik, accession_no)` is a source-identity/dedup key, not a
"never touch again" flag: `rule_version` separates *processing outcome*
from *source identity*, so a future rule/AI-model change or an explicit
`--force-reprocess` run can deliberately re-evaluate an already-seen filing
by updating this row in place — it never inserts a second row for the same
filing, and it never makes historical re-evaluation architecturally
impossible (see ARCHITECTURE_DECISIONS.md and PLAN.md Milestone 7.5 for the
full rationale).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import MarketDiscoveryResolutionOutcome
from app.db.base import Base

_OUTCOME_SQL_LIST = ", ".join(f"'{value}'" for value in MarketDiscoveryResolutionOutcome)


class MarketDiscoveryCandidate(Base):
    __tablename__ = "market_discovery_candidate"
    __table_args__ = (
        UniqueConstraint("cik", "accession_no", name="uq_market_discovery_candidate_cik_accession"),
        CheckConstraint(
            f"resolution_outcome IN ({_OUTCOME_SQL_LIST})",
            name="ck_market_discovery_candidate_resolution_outcome",
        ),
        Index("ix_market_discovery_candidate_discovery_run_id", "discovery_run_id"),
        Index("ix_market_discovery_candidate_issuer_id", "issuer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    discovery_run_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("market_discovery_run.id"), nullable=False
    )
    cik: Mapped[str] = mapped_column(Text, nullable=False)
    accession_no: Mapped[str] = mapped_column(Text, nullable=False)
    form_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_date: Mapped[date] = mapped_column(Date, nullable=False)
    matched_query: Mapped[str] = mapped_column(Text, nullable=False)
    sec_items: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    resolution_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_reason: Mapped[str] = mapped_column(Text, nullable=False)
    issuer_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=True
    )
    layer1_matched: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    evidence_created: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    provenance_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provenance.id"), nullable=True
    )
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
