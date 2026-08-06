"""Integration tests for issuer_service against the live nexus schema."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.types import FormType, InstrumentType
from app.domain.financial_fact import FinancialFactCreate
from app.domain.issuer import IssuerCreate
from app.domain.security import SecurityCreate
from app.repositories import (
    financial_fact_repository,
    issuer_repository,
    provenance_repository,
    security_repository,
)
from app.services import issuer_service
from tests.integration.conftest import reported_public_provenance


def _seed_issuer_with_a_security_and_a_filing(db: Session, *, legal_name: str) -> uuid.UUID:
    issuer_provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    issuer = issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=issuer_provenance.id)
    )

    security_provenance = provenance_repository.create_provenance(
        db, reported_public_provenance(source_record_id=f"{legal_name}-bond")
    )
    security_repository.create_security(
        db,
        SecurityCreate(
            issuer_id=issuer.id,
            instrument_type=InstrumentType.BOND,
            description=f"{legal_name} — Test Bond",
            maturity_date=date(2030, 1, 1),
            amount_outstanding=Decimal("500000000"),
            provenance_id=security_provenance.id,
        ),
    )

    fact_provenance = provenance_repository.create_provenance(
        db, reported_public_provenance(source_record_id=f"{legal_name}-10k")
    )
    financial_fact_repository.create_financial_fact(
        db,
        FinancialFactCreate(
            issuer_id=issuer.id,
            concept="us-gaap:Revenues",
            value=Decimal("1000000000"),
            unit="USD",
            fiscal_period="FY",
            fiscal_year=2025,
            form_type=FormType.FORM_10K,
            filing_date=date(2026, 2, 1),
            accession_no=f"0000000000-26-{legal_name[:6]}",
            provenance_id=fact_provenance.id,
        ),
    )
    return issuer.id


def test_get_issuer_detail_returns_none_for_missing_issuer(db_session: Session) -> None:
    assert issuer_service.get_issuer_detail(db_session, uuid.uuid4()) is None


def test_get_issuer_detail_assembles_identity_and_securities(db_session: Session) -> None:
    issuer_id = _seed_issuer_with_a_security_and_a_filing(
        db_session, legal_name="Issuer Service Test Co Alpha"
    )

    detail = issuer_service.get_issuer_detail(db_session, issuer_id)

    assert detail is not None
    assert detail.legal_name == "Issuer Service Test Co Alpha"
    assert len(detail.securities) == 1
    assert detail.securities[0].amount_outstanding == Decimal("500000000")


def test_get_issuer_detail_includes_financial_facts(db_session: Session) -> None:
    issuer_id = _seed_issuer_with_a_security_and_a_filing(
        db_session, legal_name="Issuer Service Test Co Beta"
    )

    detail = issuer_service.get_issuer_detail(db_session, issuer_id)

    assert detail is not None
    assert len(detail.financial_facts) == 1
    assert detail.financial_facts[0].concept == "us-gaap:Revenues"
    assert detail.financial_facts[0].form_type is FormType.FORM_10K


def test_get_issuer_detail_data_sources_counts_every_provider(db_session: Session) -> None:
    issuer_id = _seed_issuer_with_a_security_and_a_filing(
        db_session, legal_name="Issuer Service Test Co Gamma"
    )

    detail = issuer_service.get_issuer_detail(db_session, issuer_id)

    assert detail is not None
    assert len(detail.data_sources) == 1
    # issuer identity + one security + one financial fact = 3 provenance records.
    assert detail.data_sources[0].record_count == 3


def test_get_issuer_detail_recent_activity_is_sorted_newest_first(db_session: Session) -> None:
    issuer_id = _seed_issuer_with_a_security_and_a_filing(
        db_session, legal_name="Issuer Service Test Co Delta"
    )

    detail = issuer_service.get_issuer_detail(db_session, issuer_id)

    assert detail is not None
    assert len(detail.recent_activity) >= 2
    occurred_dates = [item.occurred_on for item in detail.recent_activity]
    assert occurred_dates == sorted(occurred_dates, reverse=True)
    categories = {item.category for item in detail.recent_activity}
    assert "security_identified" in categories
    assert "filing" in categories
