"""Integration tests for financial_fact_repository against the live nexus schema."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.types import FormType
from app.domain.financial_fact import FinancialFactCreate
from app.domain.issuer import IssuerCreate
from app.models.financial_fact import FinancialFact as FinancialFactModel
from app.repositories import financial_fact_repository as repo
from app.repositories import issuer_repository, provenance_repository
from tests.integration.conftest import reported_public_provenance


def _issuer_id(db: Session) -> uuid.UUID:
    # cik=None (not a real SEC filer) to avoid any risk of colliding with the
    # genuine Apple issuer row intentionally left committed in the live
    # database as evidence of the SEC ingestion pipeline (see
    # test_issuer_repository.py's _issuer_create docstring for the same note).
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    issuer = issuer_repository.create_issuer(
        db, IssuerCreate(legal_name="Test Issuer Co", cik=None, provenance_id=provenance.id)
    )
    return issuer.id


def _fact_create(db: Session, issuer_id: uuid.UUID, **overrides: object) -> FinancialFactCreate:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    defaults: dict[str, object] = dict(
        issuer_id=issuer_id,
        concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        value=Decimal("416161000000"),
        unit="USD",
        fiscal_period="FY",
        fiscal_year=2025,
        form_type=FormType.FORM_10K,
        filing_date=date(2025, 10, 31),
        accession_no="0000320193-25-000079",
        provenance_id=provenance.id,
    )
    defaults.update(overrides)
    return FinancialFactCreate(**defaults)  # type: ignore[arg-type]


def test_create_and_get_financial_fact(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    created = repo.create_financial_fact(db_session, _fact_create(db_session, issuer_id))
    assert created.id is not None

    fetched = repo.get_financial_fact(db_session, created.id)
    assert fetched is not None
    assert fetched.value == Decimal("416161000000")
    assert isinstance(fetched.value, Decimal)
    assert fetched.form_type is FormType.FORM_10K


def test_get_financial_fact_missing_returns_none(db_session: Session) -> None:
    assert repo.get_financial_fact(db_session, uuid.uuid4()) is None


def test_list_financial_facts_by_issuer(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    repo.create_financial_fact(
        db_session, _fact_create(db_session, issuer_id, concept="Revenues", fiscal_year=2024)
    )
    repo.create_financial_fact(
        db_session, _fact_create(db_session, issuer_id, concept="NetIncomeLoss", fiscal_year=2024)
    )

    facts = repo.list_financial_facts_by_issuer(db_session, issuer_id)

    assert {f.concept for f in facts} == {"Revenues", "NetIncomeLoss"}


def test_get_by_dedup_key_finds_existing(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    repo.create_financial_fact(db_session, _fact_create(db_session, issuer_id))

    found = repo.get_by_dedup_key(
        db_session,
        issuer_id,
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "0000320193-25-000079",
        2025,
        "FY",
    )

    assert found is not None


def test_get_by_dedup_key_not_found_returns_none(db_session: Session) -> None:
    issuer_id = _issuer_id(db_session)
    found = repo.get_by_dedup_key(
        db_session, issuer_id, "NoSuchConcept", "0000000000-00-000000", 2020, "FY"
    )
    assert found is None


def test_dedup_unique_index_enforced_at_db_level(db_session: Session) -> None:
    """Defense-in-depth: ix_financial_fact_dedup rejects re-ingesting the
    exact same issuer/concept/accession/fy/fp combination."""
    issuer_id = _issuer_id(db_session)
    repo.create_financial_fact(db_session, _fact_create(db_session, issuer_id))

    with pytest.raises(IntegrityError):
        repo.create_financial_fact(db_session, _fact_create(db_session, issuer_id))


def test_form_type_check_constraint_enforced_at_db_level(db_session: Session) -> None:
    """Defense-in-depth: form_type must be one of the CHECK-constrained values,
    even bypassing the Pydantic/FormType layer."""
    issuer_id = _issuer_id(db_session)
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    bad_row = FinancialFactModel(
        issuer_id=issuer_id,
        concept="Revenues",
        value=Decimal("1"),
        unit="USD",
        fiscal_period="FY",
        fiscal_year=2025,
        form_type="not-a-real-form",
        filing_date=date(2025, 1, 1),
        accession_no="0000000000-00-000000",
        provenance_id=provenance.id,
    )
    db_session.add(bad_row)
    with pytest.raises(IntegrityError, match="ck_financial_fact_form_type"):
        db_session.flush()
