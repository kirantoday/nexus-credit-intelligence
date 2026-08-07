"""Repository for `court_docket_link_attempt` (PLAN.md Milestone 7.5 section 10, ADR-020).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import CourtDocketLinkMatchOutcome
from app.domain.court_docket_link_attempt import (
    CourtDocketLinkAttempt,
    CourtDocketLinkAttemptCreate,
)
from app.models.court_docket_link_attempt import CourtDocketLinkAttempt as AttemptModel


def _to_domain(row: AttemptModel) -> CourtDocketLinkAttempt:
    return CourtDocketLinkAttempt(
        id=row.id,
        issuer_id=row.issuer_id,
        query_used=row.query_used,
        candidate_courtlistener_docket_id=row.candidate_courtlistener_docket_id,
        match_outcome=CourtDocketLinkMatchOutcome(row.match_outcome),
        match_signals=row.match_signals,
        linked_docket_id=row.linked_docket_id,
        created_at=row.created_at,
    )


def create_attempt(db: Session, data: CourtDocketLinkAttemptCreate) -> CourtDocketLinkAttempt:
    row = AttemptModel(
        issuer_id=data.issuer_id,
        query_used=data.query_used,
        candidate_courtlistener_docket_id=data.candidate_courtlistener_docket_id,
        match_outcome=data.match_outcome.value,
        match_signals=data.match_signals,
        linked_docket_id=data.linked_docket_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def list_attempts_for_issuer(db: Session, issuer_id: UUID) -> list[CourtDocketLinkAttempt]:
    stmt = (
        select(AttemptModel)
        .where(AttemptModel.issuer_id == issuer_id)
        .order_by(AttemptModel.created_at.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_domain(row) for row in rows]
