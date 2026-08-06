"""Response schemas for the Capital Structure API (PLAN.md section 7).

Answers "what debt exists, which instrument sits where, what's secured vs.
unsecured" for one issuer: the full stack, ordered top (most senior) to
bottom. `enterprise_value_coverage`/`illustrative_recovery` are `None` for
any issuer/layer this platform hasn't modeled a scenario for — never a
guessed number. When either is present, `recovery_scenario` is always
present alongside it (enforced already at the domain layer,
`app/domain/capital_structure.py`), so the frontend can render PLAN.md
section 7's mandatory four-part label ("calculated, scenario-based,
illustrative, not a market fact") every time, not just once.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.freshness import FreshnessTier
from app.core.types import (
    CapitalStructureInstrumentType,
    DataClassification,
    ProviderName,
    Seniority,
    TransformationType,
)


class CapitalStructurePositionRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    position_id: UUID
    security_id: UUID | None
    layer_name: str
    rank_order: int
    instrument_type: CapitalStructureInstrumentType
    seniority: Seniority | None
    lien_position: str | None
    secured: bool
    guarantor_scope: str | None
    amount_outstanding: Decimal
    currency: str
    maturity_date: date | None
    price: Decimal | None
    enterprise_value_coverage: Decimal | None
    illustrative_recovery: Decimal | None
    recovery_scenario: str | None
    is_synthetic: bool
    synthetic_reason: str | None
    provider: ProviderName
    classification: DataClassification
    transformation: TransformationType
    as_of_date: date
    retrieved_at: datetime
    freshness: FreshnessTier


class CapitalStructureResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_id: UUID
    issuer_legal_name: str
    positions: list[CapitalStructurePositionRow]
