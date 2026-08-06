"""Repository for `data_entitlement`.

See `provenance_repository.py`'s module docstring for this project's
repository conventions. `find_active_entitlement` is what a route/service calls
before `app.core.entitlement.policy_check` — resolving the entitlement is I/O
(this repository's job), deciding on it is pure (`policy_check`'s job).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import EnvironmentName, ProviderName
from app.domain.entitlement import DataEntitlement, DataEntitlementCreate
from app.models.entitlement import DataEntitlement as DataEntitlementModel


def _to_domain(row: DataEntitlementModel) -> DataEntitlement:
    return DataEntitlement(
        id=row.id,
        provider=ProviderName(row.provider),
        dataset=row.dataset,
        legal_entity=row.legal_entity,
        environment=EnvironmentName(row.environment),
        permitted_users=row.permitted_users,
        permitted_use=row.permitted_use,
        storage_allowed=row.storage_allowed,
        retention_period_days=row.retention_period_days,
        derived_data_permission=row.derived_data_permission,
        ai_processing_permission=row.ai_processing_permission,
        embedding_permission=row.embedding_permission,
        display_permission=row.display_permission,
        redistribution_permission=row.redistribution_permission,
        effective_date=row.effective_date,
        expiration_date=row.expiration_date,
        contract_reference=row.contract_reference,
    )


def create_entitlement(db: Session, data: DataEntitlementCreate) -> DataEntitlement:
    row = DataEntitlementModel(
        provider=data.provider.value,
        dataset=data.dataset,
        legal_entity=data.legal_entity,
        environment=data.environment.value,
        permitted_users=data.permitted_users,
        permitted_use=data.permitted_use,
        storage_allowed=data.storage_allowed,
        retention_period_days=data.retention_period_days,
        derived_data_permission=data.derived_data_permission,
        ai_processing_permission=data.ai_processing_permission,
        embedding_permission=data.embedding_permission,
        display_permission=data.display_permission,
        redistribution_permission=data.redistribution_permission,
        effective_date=data.effective_date,
        expiration_date=data.expiration_date,
        contract_reference=data.contract_reference,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_entitlement(db: Session, entitlement_id: UUID) -> DataEntitlement | None:
    row = db.get(DataEntitlementModel, entitlement_id)
    return _to_domain(row) if row is not None else None


def find_active_entitlement(
    db: Session,
    provider: str,
    dataset: str,
    legal_entity: str,
    environment: str,
    as_of: date,
) -> DataEntitlement | None:
    """Find the entitlement covering `as_of`, if any.

    Most-recently-effective match wins if more than one row happens to cover
    the same date (shouldn't normally happen, but is not itself invalid).
    """
    stmt = (
        select(DataEntitlementModel)
        .where(
            DataEntitlementModel.provider == provider,
            DataEntitlementModel.dataset == dataset,
            DataEntitlementModel.legal_entity == legal_entity,
            DataEntitlementModel.environment == environment,
            DataEntitlementModel.effective_date <= as_of,
        )
        .where(
            (DataEntitlementModel.expiration_date.is_(None))
            | (DataEntitlementModel.expiration_date >= as_of)
        )
        .order_by(DataEntitlementModel.effective_date.desc())
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None
