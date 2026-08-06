"""Canonical domain object for `issuer` (PLAN.md section 4.5).

Provider-neutral by design: SEC EDGAR populates it today, but the exact same
shape must be populable by OpenFIGI, Bloomberg, S&P Global, or any future
provider — no SEC-specific fields (e.g. a raw CIK-only identifier scheme, SIC
description text) leak into this object beyond the fields PLAN.md's schema
already names.

`is_synthetic`/`synthetic_reason` follow PLAN.md 4.5's `synthetic_flag`
pattern ("every synthetic row sets `classification = synthetic` on its
provenance AND carries a denormalized `is_synthetic` boolean... tagged
`SYNTHETIC_DEMO_DATA` in a `synthetic_reason` column") — added in Milestone 4,
the first milestone that creates any synthetic issuer (the leveraged loan
generator's fictional demo companies).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class IssuerCreate(BaseModel):
    """Everything needed to create an `issuer` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    legal_name: str
    cik: str | None = None
    lei: str | None = None
    ticker: str | None = None
    sic: str | None = None
    sector: str | None = None
    is_synthetic: bool = False
    synthetic_reason: str | None = None
    provenance_id: UUID

    @model_validator(mode="after")
    def _synthetic_reason_requires_is_synthetic(self) -> IssuerCreate:
        if self.synthetic_reason is not None and not self.is_synthetic:
            raise ValueError("synthetic_reason may only be set when is_synthetic is True")
        return self


class Issuer(IssuerCreate):
    """A persisted `issuer` row."""

    id: UUID
