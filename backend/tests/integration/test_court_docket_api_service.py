"""Integration tests for court_docket_api_service against the live nexus schema."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.types import DocketDocumentAvailability
from app.domain.court_docket import CourtDocketCreate
from app.domain.court_docket_entry import CourtDocketEntryCreate
from app.domain.docket_document import DocketDocumentCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.repositories import (
    court_docket_entry_repository,
    court_docket_repository,
    docket_document_repository,
    issuer_repository,
    provenance_repository,
)
from app.services import court_docket_api_service
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str) -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    )


def test_list_dockets_filters_by_issuer(db_session: Session) -> None:
    issuer_in = _seed_issuer(db_session, legal_name=f"Docket API Test Co In {uuid4()}")
    issuer_out = _seed_issuer(db_session, legal_name=f"Docket API Test Co Out {uuid4()}")
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=issuer_in.id,
            courtlistener_docket_id=uuid4().int % 900000,
            court="Test Court",
            docket_number="24-API-1",
            case_name="In Scope Docket Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2024, 1, 1),
            provenance_id=provenance.id,
        ),
    )
    court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=issuer_out.id,
            courtlistener_docket_id=uuid4().int % 900000,
            court="Test Court",
            docket_number="24-API-2",
            case_name="Out of Scope Docket Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2024, 1, 1),
            provenance_id=provenance.id,
        ),
    )

    response = court_docket_api_service.list_dockets(db_session, issuer_id=issuer_in.id)

    assert len(response.dockets) == 1
    assert response.dockets[0].issuer_id == issuer_in.id
    assert response.dockets[0].issuer_legal_name == issuer_in.legal_name
    assert response.dockets[0].courtlistener_url.startswith("https://www.courtlistener.com/docket/")


def test_get_docket_detail_includes_entries_and_documents(db_session: Session) -> None:
    issuer = _seed_issuer(db_session, legal_name=f"Docket Detail Test Co {uuid4()}")
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    docket, _created = court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=issuer.id,
            courtlistener_docket_id=uuid4().int % 900000,
            court="Test Court",
            docket_number="24-API-3",
            case_name="Docket Detail Test Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2024, 1, 1),
            provenance_id=provenance.id,
        ),
    )
    entry_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    entry, _created = court_docket_entry_repository.create_entry(
        db_session,
        CourtDocketEntryCreate(
            docket_id=docket.id,
            courtlistener_entry_id=uuid4().int % 900000,
            entry_number=1,
            entry_date=date(2024, 1, 1),
            description="Chapter 11 Voluntary Petition Filed.",
            document_available=True,
            provenance_id=entry_provenance.id,
        ),
    )
    document_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    docket_document_repository.create_document(
        db_session,
        DocketDocumentCreate(
            docket_entry_id=entry.id,
            courtlistener_document_id=uuid4().int % 900000,
            availability=DocketDocumentAvailability.RECAP_AVAILABLE,
            description="Voluntary Petition",
            page_count=25,
            is_sealed=False,
            recap_document_url="https://www.courtlistener.com/docket/test-doc/",
            raw_payload_id=None,
            provenance_id=document_provenance.id,
        ),
    )

    detail = court_docket_api_service.get_docket_detail(db_session, docket.id)

    assert detail is not None
    assert detail.docket.case_name == "Docket Detail Test Co"
    assert len(detail.entries) == 1
    assert detail.entries[0].document_available is True
    assert len(detail.entries[0].documents) == 1
    assert detail.entries[0].documents[0].availability is DocketDocumentAvailability.RECAP_AVAILABLE


def test_get_docket_detail_returns_none_for_unknown_docket(db_session: Session) -> None:
    result = court_docket_api_service.get_docket_detail(db_session, uuid4())
    assert result is None


def test_list_dockets_with_no_issuer_filter_returns_only_linked_dockets(
    db_session: Session,
) -> None:
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=None,
            courtlistener_docket_id=uuid4().int % 900000,
            court="Test Court",
            docket_number="24-API-4",
            case_name="Unlinked Docket Co",
            nature_of_suit=None,
            chapter=None,
            date_filed=None,
            provenance_id=provenance.id,
        ),
    )

    response = court_docket_api_service.list_dockets(db_session)

    assert all(d.issuer_id is not None for d in response.dockets)
    assert not any(d.case_name == "Unlinked Docket Co" for d in response.dockets)
