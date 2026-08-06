"""Canonical domain object for `issuer` (PLAN.md section 4.5).

Provider-neutral by design: SEC EDGAR populates it today, but the exact same
shape must be populable by OpenFIGI, Bloomberg, S&P Global, or any future
provider — no SEC-specific fields (e.g. a raw CIK-only identifier scheme, SIC
description text) leak into this object beyond the fields PLAN.md's schema
already names.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IssuerCreate(BaseModel):
    """Everything needed to create an `issuer` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    legal_name: str
    cik: str | None = None
    lei: str | None = None
    ticker: str | None = None
    sic: str | None = None
    sector: str | None = None
    provenance_id: UUID


class Issuer(IssuerCreate):
    """A persisted `issuer` row."""

    id: UUID
