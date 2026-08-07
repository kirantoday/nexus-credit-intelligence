"""ORM model for `court_docket_link_attempt` (PLAN.md Milestone 7.5 section 10, ADR-020).

Every automatic CourtListener docket-linking attempt (successful or not)
gets its own row, distinct from `issuer_enrichment_status`'s single
current-state row, so a rejected/ambiguous attempt stays diagnosable
without being overwritten by the next retry. `match_signals` records the
full evaluated signal set (pass/fail/not-available per signal) so every
auto-link decision is auditable, not a black box — required given ADR-020
supersedes ADR-019's blanket prohibition on automatic linking.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import CourtDocketLinkMatchOutcome
from app.db.base import Base

_OUTCOME_SQL_LIST = ", ".join(f"'{value}'" for value in CourtDocketLinkMatchOutcome)


class CourtDocketLinkAttempt(Base):
    __tablename__ = "court_docket_link_attempt"
    __table_args__ = (
        CheckConstraint(
            f"match_outcome IN ({_OUTCOME_SQL_LIST})",
            name="ck_court_docket_link_attempt_match_outcome",
        ),
        Index("ix_court_docket_link_attempt_issuer_id", "issuer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    query_used: Mapped[str] = mapped_column(Text, nullable=False)
    candidate_courtlistener_docket_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    match_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    match_signals: Mapped[dict] = mapped_column(JSONB, nullable=False)
    linked_docket_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("court_docket.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
