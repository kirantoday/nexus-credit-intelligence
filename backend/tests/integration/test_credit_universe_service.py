"""Integration tests for credit_universe_service against the live nexus schema."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.freshness import FreshnessTier
from app.core.types import InstrumentType
from app.domain.issuer import IssuerCreate
from app.domain.security import SecurityCreate
from app.repositories import issuer_repository, provenance_repository, security_repository
from app.services import credit_universe_service
from tests.integration.conftest import reported_public_provenance


def _seed_one_security(db: Session, *, legal_name: str) -> None:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    issuer = issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    )
    security_repository.create_security(
        db,
        SecurityCreate(
            issuer_id=issuer.id,
            instrument_type=InstrumentType.BOND,
            description=f"{legal_name} — Test Bond",
            maturity_date=date(2030, 1, 1),
            amount_outstanding=Decimal("500000000"),
            provenance_id=provenance.id,
        ),
    )


def test_get_credit_universe_page_returns_assembled_rows(db_session: Session) -> None:
    _seed_one_security(db_session, legal_name="Service Test Issuer Alpha")

    page = credit_universe_service.get_credit_universe_page(
        db_session, search="Service Test Issuer Alpha"
    )

    assert page.total == 1
    assert len(page.rows) == 1
    row = page.rows[0]
    assert row.issuer_legal_name == "Service Test Issuer Alpha"
    assert row.instrument_type is InstrumentType.BOND
    assert row.amount_outstanding == Decimal("500000000")
    assert row.freshness is FreshnessTier.LIVE, "just-created row should be freshly retrieved"
    assert row.provider is not None
    assert row.classification is not None


def test_get_credit_universe_page_pagination_metadata(db_session: Session) -> None:
    _seed_one_security(db_session, legal_name="Service Test Issuer Beta")

    page = credit_universe_service.get_credit_universe_page(
        db_session, search="Service Test Issuer Beta", page=1, page_size=10
    )

    assert page.page == 1
    assert page.page_size == 10


def test_get_credit_universe_page_empty_search_returns_empty_page(db_session: Session) -> None:
    page = credit_universe_service.get_credit_universe_page(
        db_session, search="NoSuchIssuerNameWillEverMatchThis"
    )

    assert page.total == 0
    assert page.rows == []
