"""Integration tests for `app/services/court_docket_service.py` against the
live nexus schema (PLAN.md sections 4.5, 15, ADR-018's Milestone 7 forward
path).

No live CourtListener network: `sync_one_docket`'s `sync_docket_entries_fn`
is injected with a fake matching `SyncDocketEntriesFn`'s Protocol, the same
pattern `test_filing_monitor_service.py` established for SEC — so
evidence/alert-synthesis logic is proven without hitting live CourtListener
on every test run.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import (
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    ProviderName,
    VerificationStatus,
)
from app.domain.collection import CollectionCreate, CollectionMembershipCreate
from app.domain.court_docket import CourtDocketCreate
from app.domain.court_docket_entry import CourtDocketEntryCreate
from app.domain.issuer import IssuerCreate
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.courtlistener.provider import DocketEntryIngestResult
from app.repositories import (
    alert_repository,
    collection_repository,
    court_docket_entry_repository,
    court_docket_repository,
    issuer_repository,
    provenance_repository,
    research_evidence_repository,
)
from app.services import court_docket_service
from tests.integration.conftest import reported_public_provenance

_BANKRUPTCY_ENTRY_TEXT = (
    "Chapter 11 Voluntary Petition Non-Individual Filed by Debtor. " "(Entered: 06/01/2023)"
)
_CLEAN_ENTRY_TEXT = "Notice of Appearance and Request for Notice Filed by counsel."
# Real, routine boilerplate from an active Chapter 11 case's docket —
# mentions "Chapter 11" without being a notable event itself. Must produce
# no evidence via court_docket_service (unlike raw match_rules), since the
# case's chapter is already a known given for any linked docket.
_ROUTINE_CHAPTER_11_BOILERPLATE_TEXT = (
    "Notice of Appearance and Request for Notice Filed in the Chapter 11 Cases."
)


def _seed_issuer(db: Session, *, legal_name: str) -> UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    ).id


def _seed_docket(db: Session, issuer_id: UUID, *, courtlistener_docket_id: int) -> object:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    docket, _created = court_docket_repository.create_docket(
        db,
        CourtDocketCreate(
            issuer_id=issuer_id,
            courtlistener_docket_id=courtlistener_docket_id,
            court="Test Bankruptcy Court",
            docket_number="24-00099",
            case_name="Test Docket Service Co",
            nature_of_suit=None,
            chapter="11",
            date_filed=date(2024, 1, 1),
            provenance_id=provenance.id,
        ),
    )
    return docket


def _fake_ingest_result(
    db: Session, docket_id: UUID, *, courtlistener_entry_id: int, text: str
) -> DocketEntryIngestResult:
    # A real `raw_provider_payload` row — needed since `court_docket_service`
    # links a fresh `provenance` row back to it per matched rule (mirrors
    # `test_filing_monitor_service.py`'s `_fake_text_result`).
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.COURTLISTENER,
        source_record_id=f"fake-entry-{courtlistener_entry_id}",
        url="https://www.courtlistener.com/docket/test/",
        raw_bytes=text.encode("utf-8"),
        payload_json={"description": text},
        content_type="application/json",
        retrieved_at=datetime.now(UTC),
    )
    entry_provenance = provenance_repository.create_provenance(
        db,
        reported_public_provenance(provider=ProviderName.COURTLISTENER, raw_payload_id=payload.id),
    )
    entry, _created = court_docket_entry_repository.create_entry(
        db,
        CourtDocketEntryCreate(
            docket_id=docket_id,
            courtlistener_entry_id=courtlistener_entry_id,
            entry_number=1,
            entry_date=date(2024, 1, 1),
            description=text,
            document_available=False,
            provenance_id=entry_provenance.id,
        ),
    )
    return DocketEntryIngestResult(
        entry=entry,
        entry_created=True,
        documents=[],
        match_text=text,
        raw_payload_id=payload.id,
        source_url="https://www.courtlistener.com/docket/test/",
        retrieved_at=entry_provenance.retrieved_at,
    )


def _http_client() -> ThrottledHttpClient:
    return ThrottledHttpClient(user_agent="court-docket-service-tests")


def test_sync_one_docket_creates_evidence_and_alert_for_bankruptcy_entry(
    db_session: Session,
) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Docket Service Test Co Alpha")
    docket = _seed_docket(db_session, issuer_id, courtlistener_docket_id=900001)

    def fake_sync(
        db: Session, http_client: ThrottledHttpClient, *, docket: object
    ) -> list[DocketEntryIngestResult]:
        return [
            _fake_ingest_result(
                db, docket.id, courtlistener_entry_id=800001, text=_BANKRUPTCY_ENTRY_TEXT  # type: ignore[attr-defined]
            )
        ]

    result = court_docket_service.sync_one_docket(
        db_session,
        _http_client(),
        None,
        docket=docket,  # type: ignore[arg-type]
        environment="test",
        is_backfill=True,
        sync_docket_entries_fn=fake_sync,
    )

    assert result.entries_discovered == 1
    assert result.alerts_created == 1

    evidence = research_evidence_repository.list_evidence(db_session, issuer_id=issuer_id)
    assert len(evidence) >= 1
    assert any(e.matched_rule == "phrase_chapter_11_petition" for e in evidence)
    assert all(e.evidence_provider == "courtlistener" for e in evidence)
    assert all(e.docket_entry_id is not None for e in evidence)

    alerts, total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert total == 1
    assert alerts[0].is_backfill is True
    assert alerts[0].primary_evidence_provider == "courtlistener"


def test_sync_one_docket_clean_entry_produces_no_evidence_or_alert(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Docket Service Test Co Beta")
    docket = _seed_docket(db_session, issuer_id, courtlistener_docket_id=900002)

    def fake_sync(
        db: Session, http_client: ThrottledHttpClient, *, docket: object
    ) -> list[DocketEntryIngestResult]:
        return [
            _fake_ingest_result(
                db, docket.id, courtlistener_entry_id=800002, text=_CLEAN_ENTRY_TEXT  # type: ignore[attr-defined]
            )
        ]

    result = court_docket_service.sync_one_docket(
        db_session,
        _http_client(),
        None,
        docket=docket,  # type: ignore[arg-type]
        environment="test",
        sync_docket_entries_fn=fake_sync,
    )

    assert result.alerts_created == 0
    _alerts, total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert total == 0


def test_sync_one_docket_routine_chapter_11_boilerplate_produces_no_evidence(
    db_session: Session,
) -> None:
    """Regression test for a real signal-to-noise problem caught live: this
    exact text genuinely matches `phrase_chapter_11_bare_mention` via raw
    `match_rules`, but a docket already known to be a Chapter 11 case must
    never turn its own routine boilerplate into evidence (see
    `app.core.distress_rules.DOCKET_EXCLUDED_RULE_IDS`)."""
    issuer_id = _seed_issuer(db_session, legal_name="Docket Service Test Co Epsilon")
    docket = _seed_docket(db_session, issuer_id, courtlistener_docket_id=900006)

    def fake_sync(
        db: Session, http_client: ThrottledHttpClient, *, docket: object
    ) -> list[DocketEntryIngestResult]:
        return [
            _fake_ingest_result(
                db,
                docket.id,  # type: ignore[attr-defined]
                courtlistener_entry_id=800006,
                text=_ROUTINE_CHAPTER_11_BOILERPLATE_TEXT,
            )
        ]

    result = court_docket_service.sync_one_docket(
        db_session,
        _http_client(),
        None,
        docket=docket,  # type: ignore[arg-type]
        environment="test",
        sync_docket_entries_fn=fake_sync,
    )

    assert result.alerts_created == 0
    evidence = research_evidence_repository.list_evidence(db_session, issuer_id=issuer_id)
    assert evidence == []


def test_sync_one_docket_is_idempotent_on_rerun(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Docket Service Test Co Gamma")
    docket = _seed_docket(db_session, issuer_id, courtlistener_docket_id=900003)

    call_count = {"n": 0}

    def fake_sync(
        db: Session, http_client: ThrottledHttpClient, *, docket: object
    ) -> list[DocketEntryIngestResult]:
        call_count["n"] += 1
        # Same courtlistener_entry_id every call -> create_entry is a
        # real get-or-create, so this simulates a genuine re-sync.
        return [
            _fake_ingest_result(
                db, docket.id, courtlistener_entry_id=800003, text=_BANKRUPTCY_ENTRY_TEXT  # type: ignore[attr-defined]
            )
        ]

    court_docket_service.sync_one_docket(
        db_session,
        _http_client(),
        None,
        docket=docket,  # type: ignore[arg-type]
        environment="test",
        sync_docket_entries_fn=fake_sync,
    )
    court_docket_service.sync_one_docket(
        db_session,
        _http_client(),
        None,
        docket=docket,  # type: ignore[arg-type]
        environment="test",
        sync_docket_entries_fn=fake_sync,
    )

    evidence = research_evidence_repository.list_evidence(db_session, issuer_id=issuer_id)
    assert len(evidence) >= 1, "must not duplicate evidence on re-sync"
    _alerts, total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert total == 1, "must not duplicate the alert for the same bundle on re-sync"
    assert call_count["n"] == 2, "the sync function itself is still called each run"


def test_sync_one_docket_requires_linked_issuer(db_session: Session) -> None:
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    docket, _created = court_docket_repository.create_docket(
        db_session,
        CourtDocketCreate(
            issuer_id=None,
            courtlistener_docket_id=900004,
            court="Test Court",
            docket_number="24-00100",
            case_name="Unlinked Docket Test Co",
            nature_of_suit=None,
            chapter=None,
            date_filed=None,
            provenance_id=provenance.id,
        ),
    )

    def fake_sync(
        db: Session, http_client: ThrottledHttpClient, *, docket: object
    ) -> list[DocketEntryIngestResult]:
        raise AssertionError("must not be called for an unlinked docket")

    try:
        court_docket_service.sync_one_docket(
            db_session,
            _http_client(),
            None,
            docket=docket,
            environment="test",
            sync_docket_entries_fn=fake_sync,
        )
        raise AssertionError("expected ValueError for an unlinked docket")
    except ValueError as exc:
        assert "link it first" in str(exc)


def test_docket_shows_up_in_research_universe_evidence_provider_filter(db_session: Session) -> None:
    """Evidence/alert API filters are already provider-agnostic (ADR-018) —
    proves a courtlistener-sourced alert is visible via the same
    `evidence_provider` filter sec_edgar alerts already use, with no
    route-layer change needed for Milestone 7."""
    issuer_id = _seed_issuer(db_session, legal_name="Docket Service Test Co Delta")
    universe = collection_repository.create_collection(
        db_session,
        CollectionCreate(
            slug="test-docket-universe",
            name="Test Docket Universe",
            description="Seeded for a court_docket_service test.",
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
            collection_id=universe.id,
            issuer_id=issuer_id,
            rationale="Test membership.",
            verification_status=VerificationStatus.VERIFIED,
        ),
    )
    docket = _seed_docket(db_session, issuer_id, courtlistener_docket_id=900005)

    def fake_sync(
        db: Session, http_client: ThrottledHttpClient, *, docket: object
    ) -> list[DocketEntryIngestResult]:
        return [
            _fake_ingest_result(
                db, docket.id, courtlistener_entry_id=800005, text=_BANKRUPTCY_ENTRY_TEXT  # type: ignore[attr-defined]
            )
        ]

    court_docket_service.sync_one_docket(
        db_session,
        _http_client(),
        None,
        docket=docket,  # type: ignore[arg-type]
        environment="test",
        sync_docket_entries_fn=fake_sync,
    )

    alerts, total = alert_repository.list_alerts(db_session, evidence_provider="courtlistener")
    assert total >= 1
    assert any(a.issuer_id == issuer_id for a in alerts)
