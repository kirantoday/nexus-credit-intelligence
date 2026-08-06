"""Integration tests for provenance_repository against the live nexus schema."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.types import DataClassification, ProviderName, TransformationType
from app.domain.provenance import CalculationCreate, CalculationInputCreate
from app.models.provenance import Provenance as ProvenanceModel
from app.repositories import provenance_repository as repo
from tests.integration.conftest import reported_public_provenance as _reported_public_provenance

_NOW = datetime.now(UTC)
_TODAY = date.today()


def test_create_and_get_provenance(db_session: Session) -> None:
    created = repo.create_provenance(db_session, _reported_public_provenance())

    assert created.id is not None
    assert created.created_at is not None
    assert created.provider is ProviderName.SEC_EDGAR

    fetched = repo.get_provenance(db_session, created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.source_record_id == created.source_record_id


def test_get_provenance_missing_returns_none(db_session: Session) -> None:
    import uuid

    assert repo.get_provenance(db_session, uuid.uuid4()) is None


def test_calculation_with_inputs_full_lineage(db_session: Session) -> None:
    # Two raw trade observations feed a VWAP calculation.
    trade_1 = repo.create_provenance(
        db_session, _reported_public_provenance(source_record_id="trade-1")
    )
    trade_2 = repo.create_provenance(
        db_session, _reported_public_provenance(source_record_id="trade-2")
    )

    calculation = repo.create_calculation(
        db_session,
        CalculationCreate(method="vwap", formula_note="volume-weighted average price"),
        inputs=[
            CalculationInputCreate(
                provenance_id=trade_1.id, input_role="trade_price", sequence_number=1
            ),
            CalculationInputCreate(
                provenance_id=trade_2.id, input_role="trade_price", sequence_number=2
            ),
        ],
    )

    fetched_calc = repo.get_calculation(db_session, calculation.id)
    assert fetched_calc is not None
    assert fetched_calc.method == "vwap"

    inputs = repo.list_calculation_inputs(db_session, calculation.id)
    assert {i.provenance_id for i in inputs} == {trade_1.id, trade_2.id}
    assert {i.calculation_id for i in inputs} == {calculation.id}

    # The VWAP output itself is a calculated provenance record.
    vwap_output = repo.create_provenance(
        db_session,
        _reported_public_provenance(
            source_record_id="vwap-2026-06-15",
            transformation=TransformationType.CALCULATED,
            calculation_id=calculation.id,
        ),
    )
    fetched_output = repo.get_provenance(db_session, vwap_output.id)
    assert fetched_output is not None
    assert fetched_output.calculation_id == calculation.id
    assert fetched_output.transformation is TransformationType.CALCULATED


def test_calculation_input_reverse_lookup_uses_provenance_id_index(db_session: Session) -> None:
    trade = repo.create_provenance(db_session, _reported_public_provenance())
    calculation = repo.create_calculation(
        db_session,
        CalculationCreate(method="last_trade", formula_note="most recent trade price"),
        inputs=[CalculationInputCreate(provenance_id=trade.id)],
    )
    inputs = repo.list_calculation_inputs(db_session, calculation.id)
    assert len(inputs) == 1
    assert inputs[0].provenance_id == trade.id


def test_calculation_linkage_check_constraint_enforced_at_db_level(db_session: Session) -> None:
    """Defense-in-depth: even bypassing the Pydantic domain layer, the DB rejects
    a 'calculated' provenance row with no calculation_id (ck_provenance_calculation_linkage).
    """
    bad_row = ProvenanceModel(
        provider=ProviderName.SEC_EDGAR.value,
        source_record_id="bad-row",
        as_of_date=_TODAY,
        retrieved_at=_NOW,
        transformation=TransformationType.CALCULATED.value,
        classification=DataClassification.PUBLIC.value,
        calculation_id=None,
    )
    db_session.add(bad_row)
    with pytest.raises(IntegrityError, match="ck_provenance_calculation_linkage"):
        db_session.flush()
    # No explicit rollback here: the db_session fixture's teardown rolls back
    # the whole outer transaction regardless, and this Postgres session is now
    # in an aborted-transaction state until that happens anyway.


def test_original_source_check_constraint_enforced_at_db_level(db_session: Session) -> None:
    """Defense-in-depth: original_source may only be set for provider='admin_upload'."""
    bad_row = ProvenanceModel(
        provider=ProviderName.SEC_EDGAR.value,
        original_source="pacer",
        source_record_id="bad-row-2",
        as_of_date=_TODAY,
        retrieved_at=_NOW,
        transformation=TransformationType.REPORTED.value,
        classification=DataClassification.PUBLIC.value,
    )
    db_session.add(bad_row)
    with pytest.raises(IntegrityError, match="ck_provenance_original_source_requires_admin_upload"):
        db_session.flush()
