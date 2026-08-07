"""Canonical domain object for `court_docket_link_attempt` (PLAN.md Milestone
7.5 section 10, ADR-020).

`match_signals` is a plain `dict` (JSONB) rather than a typed structure —
the evaluated signal set is inherently variable (some signals are not
always available, e.g. no case number was referenced in the triggering
evidence), and this table's entire purpose is an honest, inspectable audit
record, not a input to further typed logic downstream.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import CourtDocketLinkMatchOutcome


class CourtDocketLinkAttemptCreate(BaseModel):
    """Everything needed to create a `court_docket_link_attempt` row."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    query_used: str
    candidate_courtlistener_docket_id: int | None = None
    match_outcome: CourtDocketLinkMatchOutcome
    match_signals: dict
    linked_docket_id: UUID | None = None


class CourtDocketLinkAttempt(CourtDocketLinkAttemptCreate):
    """A persisted `court_docket_link_attempt` row."""

    id: UUID
    created_at: datetime
