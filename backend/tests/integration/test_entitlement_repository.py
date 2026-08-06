"""Integration tests for entitlement_repository against the live nexus schema."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.entitlement import PolicyContext, policy_check
from app.core.types import DataClassification, EntitlementAction, EnvironmentName, ProviderName
from app.domain.entitlement import DataEntitlementCreate
from app.repositories import entitlement_repository as repo

_TODAY = date.today()


def _entitlement(**overrides: object) -> DataEntitlementCreate:
    defaults: dict[str, object] = dict(
        provider=ProviderName.SP_GLOBAL_LOAN_PRICING,
        dataset="loan_pricing",
        legal_entity="Nexus LLC",
        environment=EnvironmentName.PRODUCTION,
        permitted_use="internal research",
        storage_allowed=True,
        derived_data_permission=True,
        ai_processing_permission=True,
        embedding_permission=True,
        display_permission=True,
        redistribution_permission=False,
        effective_date=_TODAY - timedelta(days=30),
        expiration_date=_TODAY + timedelta(days=30),
        contract_reference="CONTRACT-INTEGRATION-001",
    )
    defaults.update(overrides)
    return DataEntitlementCreate(**defaults)  # type: ignore[arg-type]


def test_create_and_get_entitlement(db_session: Session) -> None:
    created = repo.create_entitlement(db_session, _entitlement())
    assert created.id is not None

    fetched = repo.get_entitlement(db_session, created.id)
    assert fetched is not None
    assert fetched.contract_reference == "CONTRACT-INTEGRATION-001"
    assert fetched.redistribution_permission is False


def test_get_entitlement_missing_returns_none(db_session: Session) -> None:
    assert repo.get_entitlement(db_session, uuid.uuid4()) is None


def test_find_active_entitlement_matches_within_window(db_session: Session) -> None:
    repo.create_entitlement(db_session, _entitlement(dataset="find-active-test-dataset"))

    found = repo.find_active_entitlement(
        db_session,
        provider=ProviderName.SP_GLOBAL_LOAN_PRICING.value,
        dataset="find-active-test-dataset",
        legal_entity="Nexus LLC",
        environment=EnvironmentName.PRODUCTION.value,
        as_of=_TODAY,
    )
    assert found is not None
    assert found.dataset == "find-active-test-dataset"


def test_find_active_entitlement_outside_window_returns_none(db_session: Session) -> None:
    repo.create_entitlement(
        db_session,
        _entitlement(
            dataset="find-active-expired-dataset",
            effective_date=_TODAY - timedelta(days=60),
            expiration_date=_TODAY - timedelta(days=30),
        ),
    )

    found = repo.find_active_entitlement(
        db_session,
        provider=ProviderName.SP_GLOBAL_LOAN_PRICING.value,
        dataset="find-active-expired-dataset",
        legal_entity="Nexus LLC",
        environment=EnvironmentName.PRODUCTION.value,
        as_of=_TODAY,
    )
    assert found is None


def test_find_active_entitlement_wrong_legal_entity_returns_none(db_session: Session) -> None:
    repo.create_entitlement(
        db_session,
        _entitlement(dataset="find-active-legal-entity-test", legal_entity="Other Corp"),
    )

    found = repo.find_active_entitlement(
        db_session,
        provider=ProviderName.SP_GLOBAL_LOAN_PRICING.value,
        dataset="find-active-legal-entity-test",
        legal_entity="Nexus LLC",
        environment=EnvironmentName.PRODUCTION.value,
        as_of=_TODAY,
    )
    assert found is None


def test_repository_lookup_feeds_policy_check_end_to_end(db_session: Session) -> None:
    """The full intended call pattern: repository resolves the entitlement,
    policy_check decides on it — proving the two layers actually compose.
    """
    repo.create_entitlement(
        db_session,
        _entitlement(
            dataset="end-to-end-dataset", display_permission=True, redistribution_permission=False
        ),
    )

    entitlement = repo.find_active_entitlement(
        db_session,
        provider=ProviderName.SP_GLOBAL_LOAN_PRICING.value,
        dataset="end-to-end-dataset",
        legal_entity="Nexus LLC",
        environment=EnvironmentName.PRODUCTION.value,
        as_of=_TODAY,
    )
    assert entitlement is not None

    context = PolicyContext(environment="production", requested_by_user_id="analyst-1")

    display_decision = policy_check(
        EntitlementAction.DISPLAY, DataClassification.LICENSED, entitlement, context
    )
    assert display_decision.allowed is True

    export_decision = policy_check(
        EntitlementAction.EXPORT, DataClassification.LICENSED, entitlement, context
    )
    assert export_decision.allowed is False
