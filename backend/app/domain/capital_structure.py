"""Canonical domain object for `capital_structure_position` (PLAN.md section 4.6).

Renders an issuer's full debt-and-equity stack in priority order (PLAN.md
section 7): revolver -> first-lien loan -> first-lien notes -> second-lien ->
unsecured -> subordinated -> preferred equity -> common equity.
`security_id` is nullable because some layers (an undrawn revolver, common
equity) have no CUSIP-bearing `security` row at all — the position is still a
real layer of the stack even without one.

`enterprise_value_coverage` / `illustrative_recovery` are the one hard
labeling requirement in this codebase (PLAN.md section 7): wherever rendered,
every one of "calculated", "scenario-based", "illustrative", and "not a
market fact" must appear, every time, not just once on a legend. The
`_recovery_requires_scenario` validator below enforces the data-layer half of
that contract — a recovery/coverage number can never reach the API without
`recovery_scenario` text describing the assumption it depends on.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import CapitalStructureInstrumentType, Seniority


class CapitalStructurePositionCreate(BaseModel):
    """Everything needed to create a `capital_structure_position` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    security_id: UUID | None = None
    layer_name: str
    rank_order: int
    instrument_type: CapitalStructureInstrumentType
    seniority: Seniority | None = None
    lien_position: str | None = None
    secured: bool
    guarantor_scope: str | None = None
    amount_outstanding: Decimal
    currency: str = "USD"
    maturity_date: date | None = None
    price: Decimal | None = None
    enterprise_value_coverage: Decimal | None = None
    illustrative_recovery: Decimal | None = None
    recovery_scenario: str | None = None
    is_synthetic: bool = False
    synthetic_reason: str | None = None
    provenance_id: UUID

    @model_validator(mode="after")
    def _synthetic_reason_requires_is_synthetic(self) -> CapitalStructurePositionCreate:
        if self.synthetic_reason is not None and not self.is_synthetic:
            raise ValueError("synthetic_reason may only be set when is_synthetic is True")
        return self

    @model_validator(mode="after")
    def _recovery_requires_scenario(self) -> CapitalStructurePositionCreate:
        has_recovery_figure = (
            self.enterprise_value_coverage is not None or self.illustrative_recovery is not None
        )
        if has_recovery_figure and self.recovery_scenario is None:
            raise ValueError(
                "recovery_scenario is required whenever enterprise_value_coverage or "
                "illustrative_recovery is set (PLAN.md section 7 labeling rule)"
            )
        return self


class CapitalStructurePosition(CapitalStructurePositionCreate):
    """A persisted `capital_structure_position` row."""

    id: UUID
