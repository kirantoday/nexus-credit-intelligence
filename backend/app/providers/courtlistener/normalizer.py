"""CourtListener DTO -> canonical domain object mapping (Milestone 7).

The only place CourtListener-specific shapes (search-result camelCase
fields, docket-entry/RECAPDocument shapes) get translated into PLAN.md's
provider-neutral canonical schema (`app/domain/court_docket.py`,
`app/domain/court_docket_entry.py`, `app/domain/docket_document.py`).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.core.types import (
    DataClassification,
    DocketDocumentAvailability,
    ProviderName,
    TransformationType,
)
from app.domain.court_docket import CourtDocketCreate
from app.domain.court_docket_entry import CourtDocketEntryCreate
from app.domain.docket_document import DocketDocumentCreate
from app.domain.provenance import ProvenanceCreate
from app.providers.courtlistener.client import absolute_courtlistener_url
from app.providers.courtlistener.dto import (
    CourtListenerSearchResultDTO,
    DocketEntryDTO,
    RecapDocumentDTO,
)


def normalize_court_docket_provenance(
    dto: CourtListenerSearchResultDTO,
    *,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.COURTLISTENER,
        source_record_id=str(dto.docket_id),
        source_url=absolute_courtlistener_url(dto.docket_absolute_url) or source_url,
        as_of_date=_parse_date(dto.dateFiled) or retrieved_at.date(),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def normalize_court_docket(
    dto: CourtListenerSearchResultDTO,
    *,
    issuer_id: UUID | None,
    provenance_id: UUID,
) -> CourtDocketCreate:
    return CourtDocketCreate(
        issuer_id=issuer_id,
        courtlistener_docket_id=dto.docket_id,
        court=dto.court or dto.court_id or "unknown",
        docket_number=dto.docketNumber,
        case_name=dto.caseName,
        nature_of_suit=dto.suitNature,
        chapter=dto.chapter,
        date_filed=_parse_date(dto.dateFiled),
        provenance_id=provenance_id,
    )


def normalize_docket_entry_provenance(
    entry: DocketEntryDTO,
    *,
    docket_source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.COURTLISTENER,
        source_record_id=str(entry.id),
        source_url=docket_source_url,
        as_of_date=_parse_date(entry.date_filed) or retrieved_at.date(),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def normalize_docket_entry(
    entry: DocketEntryDTO,
    *,
    docket_id: UUID,
    provenance_id: UUID,
) -> CourtDocketEntryCreate:
    document_available = any(
        doc.is_available and not doc.is_sealed_or_unknown for doc in entry.recap_documents
    )
    return CourtDocketEntryCreate(
        docket_id=docket_id,
        courtlistener_entry_id=entry.id,
        entry_number=entry.entry_number,
        entry_date=_parse_date(entry.date_filed),
        description=entry.description or "(no description on file)",
        document_available=document_available,
        provenance_id=provenance_id,
    )


def normalize_docket_document_provenance(
    document: RecapDocumentDTO,
    *,
    entry_source_url: str,
    entry_date: date | None,
    retrieved_at: datetime,
    raw_payload_id: UUID | None,
) -> ProvenanceCreate:
    return ProvenanceCreate(
        provider=ProviderName.COURTLISTENER,
        source_record_id=str(document.id),
        source_url=absolute_courtlistener_url(document.absolute_url) or entry_source_url,
        as_of_date=entry_date or retrieved_at.date(),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def normalize_docket_document(
    document: RecapDocumentDTO,
    *,
    docket_entry_id: UUID,
    provenance_id: UUID,
    raw_payload_id: UUID | None,
) -> DocketDocumentCreate:
    """Never marks a sealed (or unknown-sealed-status) document
    `recap_available`, regardless of what the API otherwise reports
    (PLAN.md section 22)."""
    is_sealed = document.is_sealed_or_unknown
    if is_sealed:
        availability = DocketDocumentAvailability.UNAVAILABLE_ADMIN_UPLOAD_NEEDED
        recap_document_url = None
        resolved_raw_payload_id = None
    elif document.is_available:
        availability = DocketDocumentAvailability.RECAP_AVAILABLE
        recap_document_url = absolute_courtlistener_url(document.absolute_url)
        resolved_raw_payload_id = raw_payload_id
    else:
        availability = DocketDocumentAvailability.UNAVAILABLE_ADMIN_UPLOAD_NEEDED
        recap_document_url = None
        resolved_raw_payload_id = None

    return DocketDocumentCreate(
        docket_entry_id=docket_entry_id,
        courtlistener_document_id=document.id,
        availability=availability,
        description=document.description,
        page_count=document.page_count,
        is_sealed=is_sealed,
        recap_document_url=recap_document_url,
        raw_payload_id=resolved_raw_payload_id,
        provenance_id=provenance_id,
    )


def normalize_docket_evidence_provenance(
    *,
    courtlistener_entry_id: int,
    entry_date: date | None,
    source_url: str,
    retrieved_at: datetime,
    raw_payload_id: UUID,
) -> ProvenanceCreate:
    """Provenance for one matched distress rule on a docket entry — a
    distinct retrieval event from the entry-metadata provenance
    `court_docket_entry.provenance_id` already carries. One fresh row per
    match (never reused across matches on the same entry), the same
    `calculation_input`-collision-avoidance pattern
    `sec_edgar.normalizer.normalize_filing_document_provenance` established.
    """
    return ProvenanceCreate(
        provider=ProviderName.COURTLISTENER,
        source_record_id=str(courtlistener_entry_id),
        source_url=source_url,
        as_of_date=entry_date or retrieved_at.date(),
        retrieved_at=retrieved_at,
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
        raw_payload_id=raw_payload_id,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
