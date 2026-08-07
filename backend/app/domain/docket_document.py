"""Canonical domain object for `docket_document` (PLAN.md sections 4.5, 15).

Never asserts availability for a sealed document, regardless of what
CourtListener otherwise reports (PLAN.md section 22 — never fetch sealed or
restricted material). `courtlistener_document_id` is CourtListener's own
RECAPDocument id, the idempotency key for re-sync. `uploaded_by`/`uploaded_at`
are reserved for the future admin-upload flow (PLAN.md section 9) — never
populated by this milestone's live ingestion, which only ever reads
already-RECAP-available material.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import DocketDocumentAvailability


class DocketDocumentCreate(BaseModel):
    """Everything needed to create a `docket_document` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    docket_entry_id: UUID
    courtlistener_document_id: int
    availability: DocketDocumentAvailability
    description: str | None = None
    page_count: int | None = None
    is_sealed: bool = False
    recap_document_url: str | None = None
    raw_payload_id: UUID | None = None
    uploaded_by: str | None = None
    uploaded_at: datetime | None = None
    provenance_id: UUID

    @model_validator(mode="after")
    def _sealed_never_recap_available(self) -> DocketDocumentCreate:
        if self.is_sealed and self.availability is DocketDocumentAvailability.RECAP_AVAILABLE:
            raise ValueError("a sealed document can never be marked recap_available")
        return self


class DocketDocument(DocketDocumentCreate):
    """A persisted `docket_document` row."""

    id: UUID
    created_at: datetime
