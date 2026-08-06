"""Integration tests for capital_structure_repository against the live nexus schema."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.types import CapitalStructureInstrumentType, Seniority
from app.domain.capital_structure import CapitalStructurePositionCreate
from app.domain.issuer import IssuerCreate
from app.models.capital_structure import CapitalStructurePosition as CapitalStructurePositionModel
from app.repositories import capital_structure_repository as repo
from app.repositories import issuer_repository, provenance_repository
from tests.integration.conftest import reported_public_provenance


def _issuer_id(db: Session, **overrides: object) -> uuid.UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    defaults: dict[str, object] = dict(legal_name="Capstruct Test Issuer Co", cik=None)
    defaults.update(overrides)
    issuer = issuer_repository.create_issuer(
        db, IssuerCreate(provenance_id=provenance.id, **defaults)  # type: ignore[arg-type]
    )
    return issuer.id


def _position_create(
    db: Session, issuer_id: uuid.UUID, **overrides: object
) -> CapitalStructurePositionCreate:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    defaults: dict[str, object] = dict(
        issuer_id=issuer_id,
        layer_name="First Lien Term Loan B",
        rank_order=1,
        instrument_type=CapitalStructureInstrumentType.FIRST_LIEN_LOAN,
        seniority=Seniority.FIRST_LIEN,
        secured=True,
        amount_outstanding=Decimal("320000000"),
        provenance_id=provenance.id,
    )
    defaults.update(overrides)
    return CapitalStructurePositionCreate(**defaults)  # type: ignore[arg-type]


def test_create_and_get_position(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    created = repo.create_position(db_session, _position_create(db_session, issuer_id))
    assert created.id is not None

    fetched = repo.get_position(db_session, created.id)
    assert fetched is not None
    assert fetched.amount_outstanding == Decimal("320000000")
    assert fetched.instrument_type is CapitalStructureInstrumentType.FIRST_LIEN_LOAN


def test_get_position_missing_returns_none(db_session: Session) -> None:
    assert repo.get_position(db_session, uuid.uuid4()) is None


def test_list_positions_by_issuer_orders_by_rank(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Rank Order Test Issuer")
    repo.create_position(
        db_session,
        _position_create(
            db_session,
            issuer_id,
            layer_name="Second Lien Notes",
            rank_order=2,
            instrument_type=CapitalStructureInstrumentType.SECOND_LIEN,
            seniority=Seniority.SECOND_LIEN,
        ),
    )
    repo.create_position(
        db_session,
        _position_create(
            db_session, issuer_id, layer_name="Revolving Credit Facility", rank_order=0
        ),
    )
    repo.create_position(db_session, _position_create(db_session, issuer_id, rank_order=1))

    positions = repo.list_positions_by_issuer(db_session, issuer_id)

    assert [p.rank_order for p in positions] == [0, 1, 2]
    assert positions[0].layer_name == "Revolving Credit Facility"


def test_list_positions_by_issuer_empty_when_none_seeded(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="No Capital Structure Issuer")
    assert repo.list_positions_by_issuer(db_session, issuer_id) == []


def test_security_id_nullable_for_revolver_and_equity_layers(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="No Security Row Issuer")
    position = repo.create_position(
        db_session,
        _position_create(
            db_session,
            issuer_id,
            layer_name="Common Equity",
            instrument_type=CapitalStructureInstrumentType.COMMON_EQUITY,
            seniority=Seniority.COMMON,
            secured=False,
            security_id=None,
        ),
    )
    assert position.security_id is None


def test_unique_rank_order_per_issuer_enforced_at_db_level(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Duplicate Rank Issuer")
    repo.create_position(db_session, _position_create(db_session, issuer_id, rank_order=1))

    with pytest.raises(IntegrityError):
        repo.create_position(
            db_session,
            _position_create(db_session, issuer_id, layer_name="Other Layer", rank_order=1),
        )


def test_instrument_type_check_constraint_enforced_at_db_level(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Bad Instrument Type Issuer")
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    bad_row = CapitalStructurePositionModel(
        issuer_id=issuer_id,
        layer_name="Bad row",
        rank_order=1,
        instrument_type="not-a-real-type",
        secured=True,
        amount_outstanding=Decimal("1000000"),
        provenance_id=provenance.id,
    )
    db_session.add(bad_row)
    with pytest.raises(IntegrityError, match="ck_capstruct_position_instrument_type"):
        db_session.flush()


def test_recovery_requires_scenario_check_constraint_enforced_at_db_level(
    db_session: Session,
) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Missing Scenario Issuer")
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    bad_row = CapitalStructurePositionModel(
        issuer_id=issuer_id,
        layer_name="Bad row",
        rank_order=1,
        instrument_type=CapitalStructureInstrumentType.FIRST_LIEN_LOAN.value,
        secured=True,
        amount_outstanding=Decimal("1000000"),
        illustrative_recovery=Decimal("100.00"),
        recovery_scenario=None,
        provenance_id=provenance.id,
    )
    db_session.add(bad_row)
    with pytest.raises(IntegrityError, match="ck_capstruct_position_recovery_requires_scenario"):
        db_session.flush()
