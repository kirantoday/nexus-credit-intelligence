"""Response schemas for the Court Docket API (PLAN.md sections 4.5, 15, Milestone 7)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import DocketDocumentAvailability


class DocketDocumentRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    availability: DocketDocumentAvailability
    description: str | None
    page_count: int | None
    is_sealed: bool
    recap_document_url: str | None


class CourtDocketEntryRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    entry_number: int | None
    entry_date: date | None
    description: str
    document_available: bool
    documents: list[DocketDocumentRow]


class CourtDocketRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    issuer_id: UUID | None
    issuer_legal_name: str | None
    courtlistener_docket_id: int
    court: str
    docket_number: str
    case_name: str
    nature_of_suit: str | None
    chapter: str | None
    date_filed: date | None
    courtlistener_url: str
    entry_count: int
    created_at: datetime


class CourtDocketDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    docket: CourtDocketRow
    entries: list[CourtDocketEntryRow]


class CourtDocketsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    dockets: list[CourtDocketRow]
