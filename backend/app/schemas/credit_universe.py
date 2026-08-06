"""Response schemas for the Credit Universe API (PLAN.md section 5).

These are the only shapes the frontend ever sees. Canonical, provider-neutral
fields only — no SEC-specific (or any other provider-specific) field name or
shape leaks through here; "provider" is reported as a *value* (which provider
sourced this fact), never as a different field per provider.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.freshness import FreshnessTier
from app.core.types import (
    DataClassification,
    InstrumentType,
    ProviderName,
    Seniority,
    TransformationType,
)


class CreditUniverseRow(BaseModel):
    """One row of the Credit Universe table: a security plus the issuer,
    provenance, and freshness context an analyst needs to trust it."""

    model_config = ConfigDict(frozen=True)

    security_id: UUID
    issuer_id: UUID
    issuer_legal_name: str
    issuer_ticker: str | None
    issuer_sector: str | None
    instrument_type: InstrumentType
    description: str
    seniority: Seniority | None
    lien_position: str | None
    secured: bool | None
    cusip: str | None
    isin: str | None
    figi: str | None
    maturity_date: date | None
    coupon: Decimal | None
    amount_outstanding: Decimal | None
    benchmark: str | None
    spread: Decimal | None
    is_synthetic: bool
    synthetic_reason: str | None
    provider: ProviderName
    classification: DataClassification
    transformation: TransformationType
    as_of_date: date
    retrieved_at: datetime
    freshness: FreshnessTier


class CreditUniversePage(BaseModel):
    """A paginated Credit Universe result set."""

    model_config = ConfigDict(frozen=True)

    rows: list[CreditUniverseRow]
    total: int
    page: int
    page_size: int
