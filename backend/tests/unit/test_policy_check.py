"""Unit tests for the entitlement engine (app/core/entitlement.py).

Pure-function tests, no database — `policy_check` must be exhaustively testable
without I/O (PLAN.md section 4.8, CLAUDE.md Testing Rules).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.entitlement import PolicyContext, policy_check
from app.core.types import DataClassification, EntitlementAction, EnvironmentName, ProviderName
from app.domain.entitlement import DataEntitlement

_TODAY = date(2026, 6, 15)
_CONTEXT = PolicyContext(environment="production", requested_by_user_id="user-1")


def _fully_permissive_entitlement(**overrides: object) -> DataEntitlement:
    defaults: dict[str, object] = dict(
        id=uuid4(),
        provider=ProviderName.SP_GLOBAL_LOAN_PRICING,
        dataset="loan_pricing",
        legal_entity="Nexus LLC",
        environment=EnvironmentName.PRODUCTION,
        permitted_users=None,
        permitted_use="internal research",
        storage_allowed=True,
        retention_period_days=None,
        derived_data_permission=True,
        ai_processing_permission=True,
        embedding_permission=True,
        display_permission=True,
        redistribution_permission=True,
        effective_date=_TODAY - timedelta(days=30),
        expiration_date=_TODAY + timedelta(days=30),
        contract_reference="CONTRACT-001",
    )
    defaults.update(overrides)
    return DataEntitlement(**defaults)  # type: ignore[arg-type]


def _ctx(**overrides: object) -> PolicyContext:
    defaults: dict[str, object] = dict(
        environment="production",
        requested_by_user_id="user-1",
        now=datetime(_TODAY.year, _TODAY.month, _TODAY.day),
    )
    defaults.update(overrides)
    return PolicyContext(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "classification",
    [DataClassification.PUBLIC, DataClassification.SYNTHETIC, DataClassification.AI_EXTRACTED],
)
def test_unlicensed_classifications_always_allowed_without_entitlement(
    classification: DataClassification,
) -> None:
    decision = policy_check(EntitlementAction.DISPLAY, classification, None, _CONTEXT)
    assert decision.allowed is True
    assert bool(decision) is True


def test_licensed_without_entitlement_is_denied() -> None:
    decision = policy_check(EntitlementAction.DISPLAY, DataClassification.LICENSED, None, _CONTEXT)
    assert decision.allowed is False
    assert "no data_entitlement" in decision.reason


def test_licensed_wrong_environment_is_denied() -> None:
    entitlement = _fully_permissive_entitlement(environment=EnvironmentName.STAGING)
    decision = policy_check(
        EntitlementAction.DISPLAY, DataClassification.LICENSED, entitlement, _ctx()
    )
    assert decision.allowed is False
    assert "environment" in decision.reason


def test_licensed_not_yet_effective_is_denied() -> None:
    entitlement = _fully_permissive_entitlement(
        effective_date=_TODAY + timedelta(days=1), expiration_date=None
    )
    decision = policy_check(
        EntitlementAction.DISPLAY, DataClassification.LICENSED, entitlement, _ctx()
    )
    assert decision.allowed is False
    assert "not yet effective" in decision.reason


def test_licensed_effective_today_is_allowed() -> None:
    entitlement = _fully_permissive_entitlement(effective_date=_TODAY, expiration_date=None)
    decision = policy_check(
        EntitlementAction.DISPLAY, DataClassification.LICENSED, entitlement, _ctx()
    )
    assert decision.allowed is True


def test_licensed_expired_is_denied() -> None:
    entitlement = _fully_permissive_entitlement(expiration_date=_TODAY - timedelta(days=1))
    decision = policy_check(
        EntitlementAction.DISPLAY, DataClassification.LICENSED, entitlement, _ctx()
    )
    assert decision.allowed is False
    assert "expired" in decision.reason


def test_licensed_expiring_today_is_still_allowed() -> None:
    entitlement = _fully_permissive_entitlement(expiration_date=_TODAY)
    decision = policy_check(
        EntitlementAction.DISPLAY, DataClassification.LICENSED, entitlement, _ctx()
    )
    assert decision.allowed is True


def test_licensed_no_expiration_never_expires() -> None:
    entitlement = _fully_permissive_entitlement(expiration_date=None)
    decision = policy_check(
        EntitlementAction.DISPLAY,
        DataClassification.LICENSED,
        entitlement,
        _ctx(now=datetime(2099, 1, 1)),
    )
    assert decision.allowed is True


def test_licensed_permitted_users_excludes_requester() -> None:
    entitlement = _fully_permissive_entitlement(permitted_users=["someone-else"])
    decision = policy_check(
        EntitlementAction.DISPLAY,
        DataClassification.LICENSED,
        entitlement,
        _ctx(requested_by_user_id="user-1"),
    )
    assert decision.allowed is False
    assert "permitted_users" in decision.reason


def test_licensed_permitted_users_no_requester_id_is_denied() -> None:
    entitlement = _fully_permissive_entitlement(permitted_users=["user-1"])
    decision = policy_check(
        EntitlementAction.DISPLAY,
        DataClassification.LICENSED,
        entitlement,
        _ctx(requested_by_user_id=None),
    )
    assert decision.allowed is False


def test_licensed_permitted_users_includes_requester_is_allowed() -> None:
    entitlement = _fully_permissive_entitlement(permitted_users=["user-1", "user-2"])
    decision = policy_check(
        EntitlementAction.DISPLAY,
        DataClassification.LICENSED,
        entitlement,
        _ctx(requested_by_user_id="user-1"),
    )
    assert decision.allowed is True


def test_licensed_empty_permitted_users_list_means_unrestricted() -> None:
    entitlement = _fully_permissive_entitlement(permitted_users=[])
    decision = policy_check(
        EntitlementAction.DISPLAY,
        DataClassification.LICENSED,
        entitlement,
        _ctx(requested_by_user_id=None),
    )
    assert decision.allowed is True


@pytest.mark.parametrize(
    ("action", "permission_field"),
    [
        (EntitlementAction.DISPLAY, "display_permission"),
        (EntitlementAction.EXPORT, "redistribution_permission"),
        (EntitlementAction.SEND_TO_LLM, "ai_processing_permission"),
        (EntitlementAction.CREATE_EMBEDDING, "embedding_permission"),
        (EntitlementAction.PROMPT_INCLUSION, "ai_processing_permission"),
        (EntitlementAction.DOCUMENT_DOWNLOAD, "redistribution_permission"),
        (EntitlementAction.API_EXPOSE, "redistribution_permission"),
    ],
)
def test_action_requires_its_specific_permission_flag(
    action: EntitlementAction, permission_field: str
) -> None:
    # Every flag on except the one this action actually needs -> denied.
    entitlement = _fully_permissive_entitlement(**{permission_field: False})
    decision = policy_check(action, DataClassification.LICENSED, entitlement, _ctx())
    assert decision.allowed is False
    assert permission_field in decision.reason

    # Only the flag this action needs is on -> allowed.
    all_off = {
        "display_permission": False,
        "redistribution_permission": False,
        "ai_processing_permission": False,
        "embedding_permission": False,
    }
    all_off[permission_field] = True
    entitlement_minimal = _fully_permissive_entitlement(**all_off)
    decision = policy_check(action, DataClassification.LICENSED, entitlement_minimal, _ctx())
    assert decision.allowed is True


def test_policy_decision_is_truthy_iff_allowed() -> None:
    allowed = policy_check(EntitlementAction.DISPLAY, DataClassification.PUBLIC, None, _CONTEXT)
    denied = policy_check(EntitlementAction.DISPLAY, DataClassification.LICENSED, None, _CONTEXT)
    assert bool(allowed) is True
    assert bool(denied) is False
