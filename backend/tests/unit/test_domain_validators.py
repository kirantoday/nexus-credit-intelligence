"""Unit tests for canonical domain object validators (app/domain/**).

These mirror the database CHECK constraints in app/models/** — the domain
layer is the primary line of defense (fails fast with a clear message before
any I/O), the DB constraints are defense-in-depth. See ARCHITECTURE_DECISIONS.md
ADR-014.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.types import (
    DataClassification,
    EnvironmentName,
    OriginalSource,
    ProviderName,
    TransformationType,
)
from app.domain.entitlement import DataEntitlementCreate
from app.domain.provenance import ProvenanceCreate
from app.domain.raw_provider_payload import RawProviderPayloadCreate

_NOW = datetime(2026, 6, 15, 12, 0, 0)
_TODAY = date(2026, 6, 15)


def _base_provenance_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = dict(
        provider=ProviderName.SEC_EDGAR,
        source_record_id="0000320193-24-000123",
        as_of_date=_TODAY,
        retrieved_at=_NOW,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
    )
    defaults.update(overrides)
    return defaults


def test_provenance_reported_without_calculation_id_is_valid() -> None:
    ProvenanceCreate(**_base_provenance_kwargs())  # type: ignore[arg-type]


def test_provenance_calculated_requires_calculation_id() -> None:
    with pytest.raises(ValidationError, match="calculation_id must be set"):
        ProvenanceCreate(
            **_base_provenance_kwargs(transformation=TransformationType.CALCULATED)  # type: ignore[arg-type]
        )


def test_provenance_reported_rejects_calculation_id() -> None:
    with pytest.raises(ValidationError, match="calculation_id must be set"):
        ProvenanceCreate(
            **_base_provenance_kwargs(  # type: ignore[arg-type]
                transformation=TransformationType.REPORTED, calculation_id=uuid4()
            )
        )


def test_provenance_calculated_with_calculation_id_is_valid() -> None:
    ProvenanceCreate(
        **_base_provenance_kwargs(  # type: ignore[arg-type]
            transformation=TransformationType.CALCULATED, calculation_id=uuid4()
        )
    )


def test_provenance_original_source_requires_admin_upload_provider() -> None:
    with pytest.raises(ValidationError, match="original_source may only be set"):
        ProvenanceCreate(
            **_base_provenance_kwargs(  # type: ignore[arg-type]
                provider=ProviderName.SEC_EDGAR, original_source=OriginalSource.PACER
            )
        )


def test_provenance_original_source_with_admin_upload_is_valid() -> None:
    ProvenanceCreate(
        **_base_provenance_kwargs(  # type: ignore[arg-type]
            provider=ProviderName.ADMIN_UPLOAD, original_source=OriginalSource.PACER
        )
    )


def test_provenance_admin_upload_without_original_source_is_valid() -> None:
    ProvenanceCreate(**_base_provenance_kwargs(provider=ProviderName.ADMIN_UPLOAD))  # type: ignore[arg-type]


def _base_payload_kwargs(**overrides: object) -> dict[str, object]:
    defaults: dict[str, object] = dict(
        provider=ProviderName.SEC_EDGAR,
        source_record_id="0000320193-24-000123",
        request_fingerprint="abc123",
        retrieved_at=_NOW,
        checksum="deadbeef",
        content_type="application/json",
    )
    defaults.update(overrides)
    return defaults


def test_raw_payload_requires_a_storage_location() -> None:
    with pytest.raises(ValidationError, match="either payload_json or storage_object_path"):
        RawProviderPayloadCreate(**_base_payload_kwargs())  # type: ignore[arg-type]


def test_raw_payload_with_inline_json_is_valid() -> None:
    RawProviderPayloadCreate(**_base_payload_kwargs(payload_json={"foo": "bar"}))  # type: ignore[arg-type]


def test_raw_payload_with_storage_object_path_is_valid() -> None:
    RawProviderPayloadCreate(
        **_base_payload_kwargs(storage_object_path="filings/aapl/10k.pdf")  # type: ignore[arg-type]
    )


def _base_entitlement_kwargs(**overrides: object) -> dict[str, object]:
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
        redistribution_permission=True,
        effective_date=_TODAY,
        contract_reference="CONTRACT-001",
    )
    defaults.update(overrides)
    return defaults


def test_entitlement_expiration_before_effective_is_rejected() -> None:
    with pytest.raises(ValidationError, match="expiration_date must be on or after"):
        DataEntitlementCreate(
            **_base_entitlement_kwargs(  # type: ignore[arg-type]
                effective_date=date(2026, 6, 15), expiration_date=date(2026, 6, 1)
            )
        )


def test_entitlement_expiration_on_effective_date_is_valid() -> None:
    DataEntitlementCreate(
        **_base_entitlement_kwargs(  # type: ignore[arg-type]
            effective_date=date(2026, 6, 15), expiration_date=date(2026, 6, 15)
        )
    )


def test_entitlement_no_expiration_is_valid() -> None:
    DataEntitlementCreate(**_base_entitlement_kwargs(expiration_date=None))  # type: ignore[arg-type]


def test_domain_objects_are_frozen() -> None:
    provenance = ProvenanceCreate(**_base_provenance_kwargs())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        provenance.source_record_id = "different"
