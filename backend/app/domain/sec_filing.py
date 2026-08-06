"""Canonical domain object for `sec_filing` (PLAN.md section 24.5).

Distinct from `financial_fact` (XBRL-datapoint-level) — represents the filing
itself, the unit the overnight monitor's watermark/delta logic keys off of.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SecFilingCreate(BaseModel):
    """Everything needed to create a `sec_filing` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    accession_no: str
    form_type: str
    filing_date: date
    period_of_report: date | None = None
    is_amendment: bool = False
    primary_document: str | None = None
    primary_document_url: str | None = None
    provenance_id: UUID


class SecFiling(SecFilingCreate):
    """A persisted `sec_filing` row."""

    id: UUID
    created_at: datetime
