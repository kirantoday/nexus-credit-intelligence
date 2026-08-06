"""Integration tests for security_repository against the live nexus schema."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.types import InstrumentType, Seniority
from app.domain.issuer import IssuerCreate
from app.domain.security import SecurityCreate
from app.models.security import Security as SecurityModel
from app.repositories import issuer_repository, provenance_repository
from app.repositories import security_repository as repo
from tests.integration.conftest import reported_public_provenance


def _issuer_id(db: Session, **overrides: object) -> uuid.UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    defaults: dict[str, object] = dict(legal_name="Test Issuer Co", cik=None)
    defaults.update(overrides)
    issuer = issuer_repository.create_issuer(
        db, IssuerCreate(provenance_id=provenance.id, **defaults)  # type: ignore[arg-type]
    )
    return issuer.id


def _security_create(db: Session, issuer_id: uuid.UUID, **overrides: object) -> SecurityCreate:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    defaults: dict[str, object] = dict(
        issuer_id=issuer_id,
        instrument_type=InstrumentType.LOAN,
        seniority=Seniority.FIRST_LIEN,
        description="Test Issuer Co — First Lien Term Loan B due 2029",
        maturity_date=date(2029, 6, 15),
        amount_outstanding=Decimal("325000000"),
        benchmark="SOFR",
        spread=Decimal("4.50"),
        provenance_id=provenance.id,
    )
    defaults.update(overrides)
    return SecurityCreate(**defaults)  # type: ignore[arg-type]


def test_create_and_get_security(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    created = repo.create_security(db_session, _security_create(db_session, issuer_id))
    assert created.id is not None

    fetched = repo.get_security(db_session, created.id)
    assert fetched is not None
    assert fetched.amount_outstanding == Decimal("325000000")
    assert fetched.seniority is Seniority.FIRST_LIEN


def test_get_security_missing_returns_none(db_session: Session) -> None:
    assert repo.get_security(db_session, uuid.uuid4()) is None


def test_list_securities_by_issuer(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    repo.create_security(db_session, _security_create(db_session, issuer_id, description="Loan A"))
    repo.create_security(db_session, _security_create(db_session, issuer_id, description="Loan B"))

    securities = repo.list_securities_by_issuer(db_session, issuer_id)

    assert {s.description for s in securities} == {"Loan A", "Loan B"}


def test_instrument_type_check_constraint_enforced_at_db_level(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    bad_row = SecurityModel(
        issuer_id=issuer_id,
        instrument_type="not-a-real-type",
        description="Bad row",
        provenance_id=provenance.id,
    )
    db_session.add(bad_row)
    with pytest.raises(IntegrityError, match="ck_security_instrument_type"):
        db_session.flush()


def test_synthetic_reason_check_constraint_enforced_at_db_level(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    bad_row = SecurityModel(
        issuer_id=issuer_id,
        instrument_type=InstrumentType.LOAN.value,
        description="Bad row",
        is_synthetic=False,
        synthetic_reason="SYNTHETIC_DEMO_DATA",
        provenance_id=provenance.id,
    )
    db_session.add(bad_row)
    with pytest.raises(IntegrityError, match="ck_security_synthetic_reason_requires_is_synthetic"):
        db_session.flush()


def test_cusip_uniqueness_enforced_when_present(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    repo.create_security(db_session, _security_create(db_session, issuer_id, cusip="123456AB1"))

    with pytest.raises(IntegrityError):
        repo.create_security(db_session, _security_create(db_session, issuer_id, cusip="123456AB1"))


def test_multiple_securities_with_null_cusip_are_allowed(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    first = repo.create_security(db_session, _security_create(db_session, issuer_id, cusip=None))
    second = repo.create_security(db_session, _security_create(db_session, issuer_id, cusip=None))
    assert first.id != second.id


def test_list_credit_universe_filters_by_instrument_type(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    repo.create_security(
        db_session, _security_create(db_session, issuer_id, instrument_type=InstrumentType.LOAN)
    )
    repo.create_security(
        db_session,
        _security_create(
            db_session, issuer_id, instrument_type=InstrumentType.BOND, description="A bond"
        ),
    )

    loans, total = repo.list_credit_universe(db_session, instrument_type=InstrumentType.LOAN)

    assert total >= 1
    assert all(row.security.instrument_type is InstrumentType.LOAN for row in loans)


def test_list_credit_universe_filters_by_is_synthetic(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    repo.create_security(db_session, _security_create(db_session, issuer_id, is_synthetic=False))
    synthetic_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    repo.create_security(
        db_session,
        SecurityCreate(
            issuer_id=issuer_id,
            instrument_type=InstrumentType.LOAN,
            description="Synthetic loan",
            is_synthetic=True,
            synthetic_reason="SYNTHETIC_DEMO_DATA",
            provenance_id=synthetic_provenance.id,
        ),
    )

    synthetic_rows, _ = repo.list_credit_universe(db_session, is_synthetic=True)
    assert all(row.security.is_synthetic for row in synthetic_rows)

    real_rows, _ = repo.list_credit_universe(db_session, is_synthetic=False)
    assert all(not row.security.is_synthetic for row in real_rows)


def test_list_credit_universe_search_matches_issuer_name(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Zzyzx Unique Search Target Corp")
    repo.create_security(db_session, _security_create(db_session, issuer_id))

    rows, total = repo.list_credit_universe(db_session, search="Zzyzx Unique Search Target")

    assert total == 1
    assert rows[0].issuer_legal_name == "Zzyzx Unique Search Target Corp"


def test_list_credit_universe_pagination(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Pagination Test Issuer")
    for i in range(5):
        repo.create_security(
            db_session, _security_create(db_session, issuer_id, description=f"Loan {i}")
        )

    page_1, total = repo.list_credit_universe(
        db_session, search="Pagination Test Issuer", page=1, page_size=2
    )
    page_2, _ = repo.list_credit_universe(
        db_session, search="Pagination Test Issuer", page=2, page_size=2
    )

    assert total == 5
    assert len(page_1) == 2
    assert len(page_2) == 2
    assert {r.security.id for r in page_1}.isdisjoint({r.security.id for r in page_2})


def test_list_credit_universe_sort_by_amount_outstanding(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Sort Test Issuer")
    repo.create_security(
        db_session,
        _security_create(
            db_session, issuer_id, description="Small", amount_outstanding=Decimal("1000")
        ),
    )
    repo.create_security(
        db_session,
        _security_create(
            db_session, issuer_id, description="Large", amount_outstanding=Decimal("9000000")
        ),
    )

    ascending, _ = repo.list_credit_universe(
        db_session,
        search="Sort Test Issuer",
        sort_by="amount_outstanding",
        sort_dir="asc",
    )

    assert [r.security.description for r in ascending] == ["Small", "Large"]


def test_list_credit_universe_includes_provenance_metadata(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session, legal_name="Provenance Metadata Issuer")
    repo.create_security(db_session, _security_create(db_session, issuer_id))

    rows, _ = repo.list_credit_universe(db_session, search="Provenance Metadata Issuer")

    assert len(rows) == 1
    row = rows[0]
    assert row.provenance_provider is not None
    assert row.provenance_as_of_date is not None
    assert row.provenance_retrieved_at is not None
