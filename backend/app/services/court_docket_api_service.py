"""Assembles Court Docket API responses (PLAN.md sections 4.5, 15, Milestone 7).

Read-only assembly for the API surface — distinct from
`app.services.court_docket_service`, which is the write-side sync
orchestrator. This module never ingests anything; it only joins
already-persisted dockets/entries/documents with issuer names for display.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.court_docket import CourtDocket
from app.domain.court_docket_entry import CourtDocketEntry
from app.repositories import (
    court_docket_entry_repository,
    court_docket_repository,
    docket_document_repository,
    issuer_repository,
)
from app.schemas.court_docket import (
    CourtDocketDetail,
    CourtDocketEntryRow,
    CourtDocketRow,
    CourtDocketsResponse,
    DocketDocumentRow,
)


def _docket_to_row(db: Session, docket: CourtDocket) -> CourtDocketRow:
    issuer = issuer_repository.get_issuer(db, docket.issuer_id) if docket.issuer_id else None
    entry_count = len(court_docket_entry_repository.list_entries_by_docket(db, docket.id))
    return CourtDocketRow(
        id=docket.id,
        issuer_id=docket.issuer_id,
        issuer_legal_name=issuer.legal_name if issuer else None,
        courtlistener_docket_id=docket.courtlistener_docket_id,
        court=docket.court,
        docket_number=docket.docket_number,
        case_name=docket.case_name,
        nature_of_suit=docket.nature_of_suit,
        chapter=docket.chapter,
        date_filed=docket.date_filed,
        courtlistener_url=(
            f"https://www.courtlistener.com/docket/{docket.courtlistener_docket_id}/"
        ),
        entry_count=entry_count,
        created_at=docket.created_at,
    )


def _entry_to_row(db: Session, entry: CourtDocketEntry) -> CourtDocketEntryRow:
    documents = docket_document_repository.list_documents_by_entry(db, entry.id)
    return CourtDocketEntryRow(
        id=entry.id,
        entry_number=entry.entry_number,
        entry_date=entry.entry_date,
        description=entry.description,
        document_available=entry.document_available,
        documents=[
            DocketDocumentRow(
                id=doc.id,
                availability=doc.availability,
                description=doc.description,
                page_count=doc.page_count,
                is_sealed=doc.is_sealed,
                recap_document_url=doc.recap_document_url,
            )
            for doc in documents
        ],
    )


def list_dockets(db: Session, *, issuer_id: UUID | None = None) -> CourtDocketsResponse:
    dockets = (
        court_docket_repository.list_dockets_by_issuer(db, issuer_id)
        if issuer_id is not None
        else court_docket_repository.list_dockets_linked_to_issuers(db)
    )
    return CourtDocketsResponse(dockets=[_docket_to_row(db, d) for d in dockets])


def get_docket_detail(db: Session, docket_id: UUID) -> CourtDocketDetail | None:
    docket = court_docket_repository.get_docket(db, docket_id)
    if docket is None:
        return None
    entries = court_docket_entry_repository.list_entries_by_docket(db, docket.id)
    return CourtDocketDetail(
        docket=_docket_to_row(db, docket),
        entries=[_entry_to_row(db, e) for e in entries],
    )
