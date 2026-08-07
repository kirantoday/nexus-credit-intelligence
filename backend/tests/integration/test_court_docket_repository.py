"""Integration tests for court_docket/court_docket_entry/docket_document
repositories (PLAN.md sections 4.5, 15, Milestone 7) against the live nexus
schema.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.types import DocketDocumentAvailability
from app.domain.court_docket import CourtDocketCreate
from app.domain.court_docket_entry import CourtDocketEntryCreate
from app.domain.docket_document import DocketDocumentCreate
from app.domain.issuer import IssuerCreate
from app.repositories import (
    court_docket_entry_repository,
    court_docket_repository,
    docket_document_repository,
    issuer_repository,
    provenance_repository,
)
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str = "Docket Test Co") -> object:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    ).id


def test_create_docket_and_get_by_courtlistener_id(db_session: Session) -> None:
    """`courtlistener_docket_id` uses the 999xxx test-only range throughout
    this file — real docket ids (e.g. Diebold Nixdorf's 67460054) are
    permanently committed live data from `app.scripts.link_court_dockets`
    and must never be reused here (a real collision was caught live: a
    get-or-create correctly returned the existing real row, `created=False`,
    when this test first used a real id by mistake)."""
    issuer_id = _seed_issuer(db_session)
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())

    docket, created = court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=issuer_id,  # type: ignore[arg-type]
            courtlistener_docket_id=999000,
            court="United States Bankruptcy Court, Test District",
            docket_number="23-90602-TEST",
            case_name="Test Docket Repository Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2023, 6, 1),
            provenance_id=provenance.id,
        ),
    )

    assert created is True
    assert docket.courtlistener_docket_id == 999000

    fetched = court_docket_repository.get_docket_by_courtlistener_id(db_session, 999000)
    assert fetched is not None
    assert fetched.id == docket.id


def test_create_docket_is_idempotent_by_courtlistener_id(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session)
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    data = CourtDocketCreate(
        issuer_id=issuer_id,  # type: ignore[arg-type]
        courtlistener_docket_id=999001,
        court="Test Court",
        docket_number="24-00001",
        case_name="Idempotency Test Co",
        nature_of_suit=None,
        chapter="11",
        date_filed=date(2024, 1, 1),
        provenance_id=provenance.id,
    )

    first, first_created = court_docket_repository.create_docket(db_session, data)
    second, second_created = court_docket_repository.create_docket(db_session, data)

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


def test_list_dockets_linked_to_issuers_excludes_unlinked(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Linked Docket Test Co")
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=issuer_id,  # type: ignore[arg-type]
            courtlistener_docket_id=999002,
            court="Test Court",
            docket_number="24-00002",
            case_name="Linked Docket Test Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2024, 1, 1),
            provenance_id=provenance.id,
        ),
    )
    court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=None,
            courtlistener_docket_id=999003,
            court="Test Court",
            docket_number="24-00003",
            case_name="Unlinked Docket Test Co",
            nature_of_suit=None,
            chapter=None,
            date_filed=None,
            provenance_id=provenance.id,
        ),
    )

    linked = court_docket_repository.list_dockets_linked_to_issuers(db_session)

    assert any(d.courtlistener_docket_id == 999002 for d in linked)
    assert not any(d.courtlistener_docket_id == 999003 for d in linked)


def test_create_entry_is_idempotent_by_courtlistener_entry_id(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session)
    docket_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    docket, _created = court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=issuer_id,  # type: ignore[arg-type]
            courtlistener_docket_id=999004,
            court="Test Court",
            docket_number="24-00004",
            case_name="Entry Idempotency Test Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2024, 1, 1),
            provenance_id=docket_provenance.id,
        ),
    )
    entry_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    data = CourtDocketEntryCreate(
        docket_id=docket.id,
        courtlistener_entry_id=555001,
        entry_number=1,
        entry_date=date(2024, 1, 1),
        description="Chapter 11 Voluntary Petition Filed.",
        document_available=False,
        provenance_id=entry_provenance.id,
    )

    first, first_created = court_docket_entry_repository.create_entry(db_session, data)
    second, second_created = court_docket_entry_repository.create_entry(db_session, data)

    assert first_created is True
    assert second_created is False
    assert first.id == second.id

    entries = court_docket_entry_repository.list_entries_by_docket(db_session, docket.id)
    assert len(entries) == 1


def test_create_document_never_recap_available_when_sealed(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session)
    docket_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    docket, _created = court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=issuer_id,  # type: ignore[arg-type]
            courtlistener_docket_id=999005,
            court="Test Court",
            docket_number="24-00005",
            case_name="Sealed Document Test Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2024, 1, 1),
            provenance_id=docket_provenance.id,
        ),
    )
    entry_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    entry, _created = court_docket_entry_repository.create_entry(
        db_session,
        CourtDocketEntryCreate(
            docket_id=docket.id,
            courtlistener_entry_id=555002,
            entry_number=2,
            entry_date=date(2024, 1, 1),
            description="Sealed filing.",
            document_available=False,
            provenance_id=entry_provenance.id,
        ),
    )
    document_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )

    document, created = docket_document_repository.create_document(
        db_session,
        DocketDocumentCreate(
            docket_entry_id=entry.id,
            courtlistener_document_id=777001,
            availability=DocketDocumentAvailability.UNAVAILABLE_ADMIN_UPLOAD_NEEDED,
            description="Sealed document",
            page_count=None,
            is_sealed=True,
            recap_document_url=None,
            raw_payload_id=None,
            provenance_id=document_provenance.id,
        ),
    )

    assert created is True
    assert document.is_sealed is True
    assert document.availability is DocketDocumentAvailability.UNAVAILABLE_ADMIN_UPLOAD_NEEDED

    documents = docket_document_repository.list_documents_by_entry(db_session, entry.id)
    assert len(documents) == 1
    assert documents[0].is_sealed is True
