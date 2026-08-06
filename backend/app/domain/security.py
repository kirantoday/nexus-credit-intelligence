"""Canonical domain object for `security` (PLAN.md section 4.5).

Provider-neutral: SEC EDGAR populates real aggregate bond data today
(`app/providers/sec_edgar/normalizer.py`'s bond extraction), the synthetic
loan generator (`app/synthetic/leveraged_loan_generator.py`) populates
clearly-tagged demo loans, and a future OpenFIGI/Bloomberg/S&P Global adapter
populates the exact same shape (filling in `cusip`/`isin`/`figi` and other
fields those providers carry) — no provider-specific field exists here.

Single `provenance_id` per row for now, not per-field (PLAN.md 4.5 notes
"each field with its own provenance row since fields arrive from different
providers"). Deferred deliberately: every Milestone 4 security's fields all
come from one ingestion event each, so a per-field lineage table would have
no real caller to validate its shape against yet — see PLAN.md Technical Debt
TD-007. It will be implemented when Milestone 5's OpenFIGI adapter actually
needs to attribute `cusip`/`isin`/`figi` separately from SEC-sourced fields
on the same row.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import InstrumentType, Seniority


class SecurityCreate(BaseModel):
    """Everything needed to create a `security` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    instrument_type: InstrumentType
    seniority: Seniority | None = None
    lien_position: str | None = None
    secured: bool | None = None
    cusip: str | None = None
    isin: str | None = None
    figi: str | None = None
    description: str
    maturity_date: date | None = None
    coupon: Decimal | None = None
    amount_outstanding: Decimal | None = None
    benchmark: str | None = None
    spread: Decimal | None = None
    is_synthetic: bool = False
    synthetic_reason: str | None = None
    provenance_id: UUID

    @model_validator(mode="after")
    def _synthetic_reason_requires_is_synthetic(self) -> SecurityCreate:
        if self.synthetic_reason is not None and not self.is_synthetic:
            raise ValueError("synthetic_reason may only be set when is_synthetic is True")
        return self


class Security(SecurityCreate):
    """A persisted `security` row."""

    id: UUID
