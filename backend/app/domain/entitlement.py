"""Canonical domain object for the entitlement engine (PLAN.md section 4.8)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import EnvironmentName, ProviderName


class DataEntitlementCreate(BaseModel):
    """Everything needed to create a `data_entitlement` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    provider: ProviderName
    dataset: str
    legal_entity: str
    environment: EnvironmentName
    permitted_users: list[str] | None = None
    permitted_use: str
    storage_allowed: bool
    retention_period_days: int | None = None
    derived_data_permission: bool
    ai_processing_permission: bool
    embedding_permission: bool
    display_permission: bool
    redistribution_permission: bool
    effective_date: date
    expiration_date: date | None = None
    contract_reference: str

    @model_validator(mode="after")
    def _expiration_on_or_after_effective(self) -> DataEntitlementCreate:
        if self.expiration_date is not None and self.expiration_date < self.effective_date:
            raise ValueError("expiration_date must be on or after effective_date")
        return self


class DataEntitlement(DataEntitlementCreate):
    """A persisted `data_entitlement` row."""

    id: UUID
