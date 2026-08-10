"""Integration tests for issuer_service against the live nexus schema."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.types import (
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    FormType,
    InstrumentType,
    VerificationStatus,
)
from app.domain.collection import CollectionCreate, CollectionMembershipCreate
from app.domain.financial_fact import FinancialFactCreate
from app.domain.issuer import IssuerCreate
from app.domain.sec_filing import SecFilingCreate
from app.domain.security import SecurityCreate
from app.repositories import (
    collection_repository,
    financial_fact_repository,
    issuer_repository,
    provenance_repository,
    sec_filing_repository,
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


def test_get_issuer_detail_includes_sec_filings_even_without_financial_facts(
    db_session: Session,
) -> None:
    """A real SEC filing on file must show up in `sec_filings` even when no
    `financial_fact` (XBRL data point) has ever been extracted from it —
    the CFO-demo polish pass's fix for the contradiction where the Distress
    Timeline showed SEC-evidence-backed events while this section claimed
    'No filings on file for this issuer yet.'"""
    issuer_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    issuer = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(legal_name="Issuer Service Test Co Zeta", provenance_id=issuer_provenance.id),
    )
    filing_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance(source_record_id="zeta-10q")
    )
    sec_filing_repository.create_filing(
        db_session,
        SecFilingCreate(
            issuer_id=issuer.id,
            accession_no="0000000000-26-000001",
            form_type="10-Q",
            filing_date=date(2026, 7, 29),
            primary_document_url="https://www.sec.gov/Archives/example.htm",
            provenance_id=filing_provenance.id,
        ),
    )

    detail = issuer_service.get_issuer_detail(db_session, issuer.id)

    assert detail is not None
    assert len(detail.financial_facts) == 0
    assert len(detail.sec_filings) == 1
    assert detail.sec_filings[0].form_type == "10-Q"
    assert detail.sec_filings[0].accession_no == "0000000000-26-000001"
    assert detail.sec_filings[0].primary_document_url == "https://www.sec.gov/Archives/example.htm"


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


def test_get_issuer_detail_includes_universe_memberships(db_session: Session) -> None:
    """Milestone 6.5 (PLAN.md 24.9) — curated Research Universe membership,
    clearly separate from factual-status sections."""
    issuer_id = _seed_issuer_with_a_security_and_a_filing(
        db_session, legal_name="Issuer Service Test Co Epsilon"
    )
    collection = collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug="test-issuer-service-universe",
            name="Test Issuer Service Universe",
            description="Seeded for an issuer_service test.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    collection_repository.add_membership(
        db_session,
        CollectionMembershipCreate(
            collection_id=collection.id,
            issuer_id=issuer_id,
            rationale="Test membership for issuer_service.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    detail = issuer_service.get_issuer_detail(db_session, issuer_id)

    assert detail is not None
    assert len(detail.universe_memberships) == 1
    assert detail.universe_memberships[0].name == "Test Issuer Service Universe"
    assert detail.universe_memberships[0].rationale == "Test membership for issuer_service."
