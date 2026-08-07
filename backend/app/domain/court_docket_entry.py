"""Canonical domain object for `court_docket_entry` (PLAN.md section 4.5, Milestone 7).

`courtlistener_entry_id` is CourtListener's own numeric entry id — the real
idempotency key. `entry_number` (PACER's docket-line number) is kept as
reported for display, but is not reliably unique or even always present
(confirmed live against real CourtListener data — some entries carry no
`entry_number` at all), so it is never used as a dedup key.
`document_available` is a single derived boolean per entry (per the frozen
schema) computed from that entry's `docket_document` rows — true only if at
least one is RECAP-available and not sealed.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CourtDocketEntryCreate(BaseModel):
    """Everything needed to create a `court_docket_entry` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    docket_id: UUID
    courtlistener_entry_id: int
    entry_number: int | None = None
    entry_date: date | None = None
    description: str
    document_available: bool = False
    provenance_id: UUID


class CourtDocketEntry(CourtDocketEntryCreate):
    """A persisted `court_docket_entry` row."""

    id: UUID
    created_at: datetime
