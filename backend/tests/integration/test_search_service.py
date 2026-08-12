"""Integration tests for `app/services/search_service.py` (PLAN.md 4.13, 8;
Milestone 12A) against the live shared `nexus` schema.

Covers: Tier 0 exact-identifier matches (CIK/ticker/CUSIP/docket-number/
accession-number) always present and never blended with fuzzy results;
full-text matches across issuer/security/alert/court-docket/docket-entry/
collection/research-note; docket-entry results carry the parent docket's
issuer/case context; archived notes and `research_note_version` content
never appear; issuer-first group ordering; empty-query handling.

Uses deliberately distinctive, made-up test data ("Zylospan") rather than
real production terms like "Chapter 11" or "covenant" — the live `nexus`
schema already has tens of thousands of real rows containing those common
words, which would make result-set assertions fragile and non-hermetic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.types import (
    AccessClassification,
    CollectionScope,
    CollectionType,
    CurationMethod,
    DataClassification,
    DetectionMethod,
    EvidenceSeverity,
    InstrumentType,
    OriginalSource,
    ProviderName,
    ResearchDocumentType,
    ThesisStatus,
    TransformationType,
    VerificationStatus,
)
from app.core.types import SearchEntityType as ET
from app.domain.alert import AlertEventCreate
from app.domain.collection import CollectionCreate
from app.domain.court_docket import CourtDocketCreate
from app.domain.court_docket_entry import CourtDocketEntryCreate
from app.domain.issuer import Issuer, IssuerCreate
from app.domain.provenance import ProvenanceCreate
from app.domain.research import ResearchNoteCreate, ResearchNoteUpdate
from app.domain.sec_filing import SecFilingCreate
from app.domain.security import SecurityCreate
from app.repositories import (
    alert_repository,
    collection_repository,
    court_docket_entry_repository,
    court_docket_repository,
    issuer_repository,
    provenance_repository,
    sec_filing_repository,
    security_repository,
)
from app.services import research_document_service, research_note_service, search_service
from app.storage.fake_storage_client import FakeStorageClient
from tests.integration.conftest import reported_public_provenance

_VALID_PDF_CONTENT = b"%PDF-1.4\n%search fixture content\n%%EOF"

_STAMP = str(uuid4())[:8]
_ISSUER_NAME = f"Zylospan Materials Corp {_STAMP}"
_CIK = f"99{_STAMP[:6]}"
_TICKER = f"ZYL{_STAMP[:4].upper()}"


def _seed_issuer(db: Session) -> Issuer:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db,
        IssuerCreate(
            legal_name=_ISSUER_NAME, cik=_CIK, ticker=_TICKER, provenance_id=provenance.id
        ),
    )


def _fixture(db: Session) -> dict[str, object]:
    """Seeds one issuer plus one row in every searchable entity type,
    all sharing the distinctive `_ISSUER_NAME`/`_STAMP` so a query for
    "Zylospan" (or the specific identifiers below) hits exactly this
    fixture's data, never real production rows."""
    issuer = _seed_issuer(db)
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())

    security = security_repository.create_security(
        db,
        SecurityCreate(
            issuer_id=issuer.id,
            instrument_type=InstrumentType.BOND,
            description=f"7.250% Senior Secured Notes due 2031 ({_ISSUER_NAME})",
            cusip=f"989{_STAMP[:6]}9",
            provenance_id=provenance.id,
        ),
    )

    alert = alert_repository.create_alert(
        db,
        AlertEventCreate(
            issuer_id=issuer.id,
            category="covenant_breach",
            severity=EvidenceSeverity.HIGH,
            headline=f"{_ISSUER_NAME} discloses restructuring advisor engagement",
            explanation=f"{_ISSUER_NAME} engaged a restructuring advisor amid liquidity pressure.",
            evidence_ids=[uuid4()],
            bundle_key=f"test-bundle-{_STAMP}",
            primary_evidence_provider="sec_edgar",
            primary_source_label="8-K",
            detection_method=DetectionMethod.DETERMINISTIC,
            ai_assisted=False,
            as_of_date=date(2026, 3, 1),
            provenance_id=provenance.id,
        ),
    )

    docket, _created = court_docket_repository.create_docket(
        db,
        CourtDocketCreate(
            issuer_id=issuer.id,
            courtlistener_docket_id=int(f"9{_STAMP[:7]}", 36) % 2_000_000_000,
            court="Test Bankruptcy Court",
            docket_number=f"99-{_STAMP[:5]}",
            case_name=f"In re {_ISSUER_NAME}",
            nature_of_suit="Bankruptcy",
            provenance_id=provenance.id,
        ),
    )

    entry, _created = court_docket_entry_repository.create_entry(
        db,
        CourtDocketEntryCreate(
            docket_id=docket.id,
            courtlistener_entry_id=int(f"8{_STAMP[:7]}", 36) % 2_000_000_000,
            entry_number=1,
            entry_date=date(2026, 3, 5),
            description=(
                f"Debtor's motion for approval of DIP financing and automatic stay "
                f"relief for {_ISSUER_NAME}."
            ),
            provenance_id=provenance.id,
        ),
    )

    collection = collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=f"zylospan-coverage-{_STAMP}",
            name=f"Zylospan Coverage Universe {_STAMP}",
            description="A test Research Universe.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            curation_method=CurationMethod.MANUAL_CURATED,
            verification_status=VerificationStatus.VERIFIED,
        ),
    )

    note = research_note_service.create_note(
        db,
        ResearchNoteCreate(
            issuer_id=issuer.id,
            title=f"{_ISSUER_NAME} — Distress Thesis",
            thesis_status=ThesisStatus.ACTIVE,
            base_case=f"{_ISSUER_NAME} stabilizes after a covenant amendment.",
            access_classification=AccessClassification.STANDARD,
        ),
    )

    document = research_document_service.upload_document(
        db,
        FakeStorageClient(),
        issuer_id=issuer.id,
        security_id=None,
        # Deliberately no "credit"/"agreement" in the title — a match on
        # those words can only come from document_type's tokenized value,
        # mirroring test_alert_category_underscore_is_tokenized.
        document_type=ResearchDocumentType.CREDIT_AGREEMENT,
        title=f"{_ISSUER_NAME} Loan Documentation",
        description=None,
        original_filename="loan-documentation.pdf",
        content=_VALID_PDF_CONTENT,
        document_date=date(2026, 3, 10),
        confidentiality_classification=AccessClassification.STANDARD,
        uploaded_by="test-analyst",
        original_source=OriginalSource.OTHER,
    )

    return {
        "issuer": issuer,
        "security": security,
        "alert": alert,
        "docket": docket,
        "entry": entry,
        "collection": collection,
        "note": note,
        "document": document,
    }


def test_empty_query_returns_empty_response(db_session: Session) -> None:
    resp = search_service.search(db_session, "   ", per_group_limit=5)
    assert resp.exact_matches == []
    assert resp.groups == []


def test_free_text_query_matches_across_entity_types(db_session: Session) -> None:
    _fixture(db_session)
    resp = search_service.search(db_session, "Zylospan", per_group_limit=10)

    group_types = {g.entity_type for g in resp.groups}
    assert ET.ISSUER in group_types
    assert ET.SECURITY in group_types
    assert ET.ALERT_EVENT in group_types
    assert ET.COURT_DOCKET in group_types
    assert ET.COURT_DOCKET_ENTRY in group_types
    assert ET.RESEARCH_NOTE in group_types
    assert ET.RESEARCH_DOCUMENT in group_types

    issuer_group = next(g for g in resp.groups if g.entity_type == ET.ISSUER)
    assert any(_ISSUER_NAME in r.title for r in issuer_group.results)


def test_issuer_group_ranks_first(db_session: Session) -> None:
    _fixture(db_session)
    resp = search_service.search(db_session, "Zylospan", per_group_limit=10)
    assert resp.groups[0].entity_type == ET.ISSUER


def test_exact_cik_match_is_tier_zero(db_session: Session) -> None:
    fixture = _fixture(db_session)
    issuer = fixture["issuer"]
    resp = search_service.search(db_session, _CIK, per_group_limit=5)
    assert len(resp.exact_matches) == 1
    assert resp.exact_matches[0].entity_type == ET.ISSUER
    assert resp.exact_matches[0].entity_id == issuer.id
    assert resp.exact_matches[0].matched_field == "CIK"


def test_exact_ticker_match_is_tier_zero(db_session: Session) -> None:
    _fixture(db_session)
    resp = search_service.search(db_session, _TICKER.lower(), per_group_limit=5)
    assert len(resp.exact_matches) == 1
    assert resp.exact_matches[0].matched_field == "Ticker"


def test_exact_cusip_match_is_tier_zero(db_session: Session) -> None:
    fixture = _fixture(db_session)
    security = fixture["security"]
    resp = search_service.search(db_session, security.cusip, per_group_limit=5)
    assert len(resp.exact_matches) == 1
    assert resp.exact_matches[0].entity_type == ET.SECURITY
    assert resp.exact_matches[0].matched_field == "CUSIP"


def test_exact_docket_number_match_is_tier_zero(db_session: Session) -> None:
    fixture = _fixture(db_session)
    docket = fixture["docket"]
    resp = search_service.search(db_session, docket.docket_number, per_group_limit=5)
    assert len(resp.exact_matches) == 1
    assert resp.exact_matches[0].entity_type == ET.COURT_DOCKET
    assert resp.exact_matches[0].matched_field == "Docket Number"


def test_exact_match_excluded_from_its_own_group(db_session: Session) -> None:
    """A hit that already appears in `exact_matches` must not also appear
    in its type's group — no duplicate rendering of the same result."""
    fixture = _fixture(db_session)
    issuer = fixture["issuer"]
    resp = search_service.search(db_session, _CIK, per_group_limit=5)
    issuer_group = next((g for g in resp.groups if g.entity_type == ET.ISSUER), None)
    if issuer_group is not None:
        assert issuer.id not in {r.entity_id for r in issuer_group.results}


def test_alert_category_underscore_is_tokenized(db_session: Session) -> None:
    """`category='covenant_breach'` must match a query for "covenant" as a
    separate word, not only the literal underscored token. Neither the
    fixture's headline nor its explanation contains "covenant" — a match
    here is only possible via the category field's underscore-to-space
    tokenization, proving that mechanism actually works."""
    fixture = _fixture(db_session)
    alert = fixture["alert"]
    # The full stamp, not a substring — to_tsvector tokenizes the
    # alphanumeric stamp as one lexeme, so a truncated prefix of it would
    # not match via websearch_to_tsquery's exact-lexeme AND semantics.
    resp = search_service.search(db_session, f"{_STAMP} covenant", per_group_limit=10)
    alert_group = next(g for g in resp.groups if g.entity_type == ET.ALERT_EVENT)
    assert any(r.entity_id == alert.id for r in alert_group.results)


def test_docket_entry_result_carries_issuer_and_case_context(db_session: Session) -> None:
    fixture = _fixture(db_session)
    entry = fixture["entry"]
    docket = fixture["docket"]
    issuer = fixture["issuer"]
    resp = search_service.search(db_session, f"DIP financing {_STAMP}", per_group_limit=10)
    entry_group = next(g for g in resp.groups if g.entity_type == ET.COURT_DOCKET_ENTRY)
    hit = next(r for r in entry_group.results if r.entity_id == entry.id)
    assert hit.issuer_id == issuer.id
    assert docket.docket_number in (hit.snippet or "")


def test_collection_group_matches_research_universe(db_session: Session) -> None:
    fixture = _fixture(db_session)
    collection = fixture["collection"]
    resp = search_service.search(db_session, f"Zylospan Coverage {_STAMP}", per_group_limit=5)
    collection_group = next(g for g in resp.groups if g.entity_type == ET.COLLECTION)
    hit = next(r for r in collection_group.results if r.entity_id == collection.id)
    assert hit.collection_type == "research_universe"


def test_research_note_group_excludes_archived_notes(db_session: Session) -> None:
    fixture = _fixture(db_session)
    note = fixture["note"]
    research_note_service.archive_note(db_session, note.id, archived_by="test")

    resp = search_service.search(db_session, _ISSUER_NAME, per_group_limit=10)
    note_group = next((g for g in resp.groups if g.entity_type == ET.RESEARCH_NOTE), None)
    if note_group is not None:
        assert note.id not in {r.entity_id for r in note_group.results}


def test_research_note_search_reflects_only_current_content_not_old_versions(
    db_session: Session,
) -> None:
    """Editing a note's title must make the *new* title searchable and the
    *old* title stop matching — proving search reads live content, never a
    stale `research_note_version` snapshot."""
    fixture = _fixture(db_session)
    note = fixture["note"]
    old_title_word = f"OldTitleWord{_STAMP}"
    new_title_word = f"NewTitleWord{_STAMP}"

    research_note_service.update_note(
        db_session, note.id, ResearchNoteUpdate(title=f"{old_title_word} thesis")
    )
    research_note_service.update_note(
        db_session, note.id, ResearchNoteUpdate(title=f"{new_title_word} thesis")
    )

    old_resp = search_service.search(db_session, old_title_word, per_group_limit=5)
    new_resp = search_service.search(db_session, new_title_word, per_group_limit=5)

    old_note_group = next((g for g in old_resp.groups if g.entity_type == ET.RESEARCH_NOTE), None)
    assert old_note_group is None or note.id not in {r.entity_id for r in old_note_group.results}

    new_note_group = next(g for g in new_resp.groups if g.entity_type == ET.RESEARCH_NOTE)
    assert note.id in {r.entity_id for r in new_note_group.results}


def test_research_document_group_matches_title(db_session: Session) -> None:
    fixture = _fixture(db_session)
    document = fixture["document"]
    resp = search_service.search(db_session, _ISSUER_NAME, per_group_limit=10)
    document_group = next(g for g in resp.groups if g.entity_type == ET.RESEARCH_DOCUMENT)
    assert document.id in {r.entity_id for r in document_group.results}


def test_research_document_type_underscore_is_tokenized(db_session: Session) -> None:
    """`document_type='credit_agreement'` must match a query for "credit
    agreement" as separate words, not only the literal underscored token.
    The fixture's title deliberately contains neither word — a match here
    is only possible via document_type's underscore-to-space tokenization,
    mirroring `test_alert_category_underscore_is_tokenized`."""
    fixture = _fixture(db_session)
    document = fixture["document"]
    resp = search_service.search(db_session, f"{_STAMP} credit agreement", per_group_limit=10)
    document_group = next(g for g in resp.groups if g.entity_type == ET.RESEARCH_DOCUMENT)
    assert document.id in {r.entity_id for r in document_group.results}


def test_research_document_group_excludes_archived_documents(db_session: Session) -> None:
    fixture = _fixture(db_session)
    document = fixture["document"]
    research_document_service.archive_document(db_session, document.id, archived_by="test")

    resp = search_service.search(db_session, _ISSUER_NAME, per_group_limit=10)
    document_group = next((g for g in resp.groups if g.entity_type == ET.RESEARCH_DOCUMENT), None)
    if document_group is not None:
        assert document.id not in {r.entity_id for r in document_group.results}


def test_research_document_search_does_not_reference_extracted_text(db_session: Session) -> None:
    """`extracted_text` is always `NULL` in Milestone 10B (no PDF
    extraction) — a query for text that would only exist in a hypothetical
    extracted PDF body must not match, proving the search_vector never
    references that column."""
    fixture = _fixture(db_session)
    document = fixture["document"]
    resp = search_service.search(
        db_session, f"{_STAMP} some-clause-that-would-only-exist-in-pdf-body", per_group_limit=10
    )
    document_group = next((g for g in resp.groups if g.entity_type == ET.RESEARCH_DOCUMENT), None)
    if document_group is not None:
        assert document.id not in {r.entity_id for r in document_group.results}


def test_sec_filing_thin_search_does_not_match_accession_number_substring(
    db_session: Session,
) -> None:
    """`search_sec_filings` (the grouped/fuzzy tier, not Tier 0) matches
    only `form_type` — a substring of a long numeric accession number must
    never coincidentally match a short numeric query."""
    issuer = _seed_issuer(db_session)
    provenance = provenance_repository.create_provenance(
        db_session,
        ProvenanceCreate(
            provider=ProviderName.SEC_EDGAR,
            source_record_id=f"test-{_STAMP}",
            as_of_date=date(2026, 1, 1),
            retrieved_at=datetime.now(UTC),
            transformation=TransformationType.REPORTED,
            classification=DataClassification.PUBLIC,
        ),
    )
    sec_filing_repository.create_filing(
        db_session,
        SecFilingCreate(
            issuer_id=issuer.id,
            accession_no=f"0009999999-26-{_STAMP[:6]}",
            form_type="8-K",
            filing_date=date(2026, 1, 1),
            provenance_id=provenance.id,
        ),
    )

    resp = search_service.search(db_session, _STAMP[:6], per_group_limit=5)
    filing_group = next((g for g in resp.groups if g.entity_type == ET.SEC_FILING), None)
    assert filing_group is None
