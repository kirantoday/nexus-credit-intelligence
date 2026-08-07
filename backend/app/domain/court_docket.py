"""Canonical domain object for `court_docket` (PLAN.md section 4.5, Milestone 7).

`issuer_id` is nullable per the frozen schema — a docket can be linked to a
known issuer once verified (this milestone's only path: an admin/seed script
explicitly links a real CourtListener docket to a real, already-verified
`issuer` row, the same live-verification discipline `seed_research_universes.py`
established in Milestone 6.5). `courtlistener_docket_id` is CourtListener's
own numeric id — the real, stable external key idempotent re-sync keys off
of, the same role `sec_filing.accession_no` plays for SEC filings.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CourtDocketCreate(BaseModel):
    """Everything needed to create a `court_docket` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID | None = None
    courtlistener_docket_id: int
    court: str
    docket_number: str
    case_name: str
    nature_of_suit: str | None = None
    chapter: str | None = None
    date_filed: date | None = None
    provenance_id: UUID


class CourtDocket(CourtDocketCreate):
    """A persisted `court_docket` row."""

    id: UUID
    created_at: datetime
