"""Canonical domain object for `financial_fact` (PLAN.md section 4.5).

`concept` is a taxonomy tag (e.g. `us-gaap:Revenues`) — provider-neutral in
shape even though only SEC EDGAR (XBRL/us-gaap) populates it today; a future
provider reporting under a different taxonomy would populate the same field
with its own tag string, not a new column.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import FormType


class FinancialFactCreate(BaseModel):
    """Everything needed to create a `financial_fact` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    concept: str
    value: Decimal
    unit: str
    fiscal_period: str
    fiscal_year: int
    form_type: FormType
    filing_date: date
    accession_no: str
    provenance_id: UUID


class FinancialFact(FinancialFactCreate):
    """A persisted `financial_fact` row."""

    id: UUID
