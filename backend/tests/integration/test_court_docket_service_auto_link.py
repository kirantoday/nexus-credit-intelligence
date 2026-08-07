"""Integration tests for `court_docket_service.attempt_auto_link` (PLAN.md
Milestone 7.5 section 10, ADR-020) against the live nexus schema.

No live CourtListener network: `search_dockets_fn`/`sync_docket_entries_fn`
are injected fakes matching the same Protocols, mirroring
`test_court_docket_service.py`'s established pattern.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.core.types import (
    CourtDocketLinkMatchOutcome,
    DetectionMethod,
    EvidenceSeverity,
    EvidenceType,
    ProviderName,
)
from app.domain.issuer import IssuerCreate
from app.domain.research_evidence import ResearchEvidenceCreate
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.courtlistener.dto import CourtListenerSearchResultDTO
from app.providers.courtlistener.provider import DocketEntryIngestResult, DocketSearchCandidate
from app.repositories import (
    court_docket_link_attempt_repository,
    court_docket_repository,
    issuer_repository,
    provenance_repository,
    research_evidence_repository,
)
from app.services import court_docket_service
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str) -> UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    ).id


def _seed_bankruptcy_evidence(
    db: Session, issuer_id: UUID, *, excerpt: str, as_of_date: date
) -> None:
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.SEC_EDGAR,
        source_record_id="fake-auto-link-filing",
        url="https://www.sec.gov/test",
        raw_bytes=excerpt.encode("utf-8"),
        payload_json={"text": excerpt},
        content_type="application/json",
        retrieved_at=datetime.now(UTC),
    )
    evidence_provenance = provenance_repository.create_provenance(
        db,
        reported_public_provenance(as_of_date=as_of_date, raw_payload_id=payload.id),
    )
    research_evidence_repository.create_evidence(
        db,
        ResearchEvidenceCreate(
            issuer_id=issuer_id,
            evidence_provider=ProviderName.SEC_EDGAR.value,
            source_type="sec_filing",
            evidence_type=EvidenceType.CHAPTER_11,
            severity=EvidenceSeverity.HIGH,
            matched_rule="phrase_chapter_11_petition",
            evidence_excerpt=excerpt,
            confidence=0.9,
            detection_method=DetectionMethod.DETERMINISTIC,
            provenance_id=evidence_provenance.id,
        ),
    )


def _search_candidate(
    db: Session, *, docket_id: int, case_name: str, docket_number: str
) -> DocketSearchCandidate:
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.COURTLISTENER,
        source_record_id=f"fake-search-{docket_id}",
        url="https://www.courtlistener.com/search",
        raw_bytes=b"{}",
        payload_json={},
        content_type="application/json",
        retrieved_at=datetime.now(UTC),
    )
    return DocketSearchCandidate(
        dto=CourtListenerSearchResultDTO(
            docket_id=docket_id,
            caseName=case_name,
            docketNumber=docket_number,
            court="United States Bankruptcy Court for the District of Delaware",
            dateFiled="2026-07-10",
            chapter="11",
        ),
        raw_payload_id=payload.id,
        source_url="https://www.courtlistener.com/search",
        retrieved_at=datetime.now(UTC),
    )


def _no_op_sync(
    db: Session, http_client: ThrottledHttpClient, *, docket: object
) -> list[DocketEntryIngestResult]:
    return []


def test_attempt_auto_link_requires_docket_relevant_evidence(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="No Evidence Co")

    with pytest.raises(ValueError, match="docket-relevant evidence"):
        court_docket_service.attempt_auto_link(
            db_session,
            None,  # type: ignore[arg-type]
            None,
            issuer_id=issuer_id,
            issuer_legal_name="No Evidence Co",
            environment="test",
            search_dockets_fn=lambda db, http_client, *, query, court: [],
        )


def test_attempt_auto_link_verified_match_links_and_syncs(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Auto Link Verified Co")
    _seed_bankruptcy_evidence(
        db_session,
        issuer_id,
        excerpt="Auto Link Verified Co filed case number 26-55555 under chapter 11.",
        as_of_date=date(2026, 7, 9),
    )
    candidate = _search_candidate(
        db_session, docket_id=888001, case_name="Auto Link Verified Co", docket_number="26-55555"
    )

    result = court_docket_service.attempt_auto_link(
        db_session,
        None,  # type: ignore[arg-type]
        None,
        issuer_id=issuer_id,
        issuer_legal_name="Auto Link Verified Co",
        environment="test",
        search_dockets_fn=lambda db, http_client, *, query, court: [candidate],
        sync_docket_entries_fn=_no_op_sync,
    )

    assert result.outcome is CourtDocketLinkMatchOutcome.VERIFIED_DOCKET_MATCH
    assert result.sync_result is not None

    linked = court_docket_repository.get_docket_by_courtlistener_id(db_session, 888001)
    assert linked is not None
    assert linked.issuer_id == issuer_id

    attempts = court_docket_link_attempt_repository.list_attempts_for_issuer(db_session, issuer_id)
    assert len(attempts) == 1
    assert attempts[0].match_outcome is CourtDocketLinkMatchOutcome.VERIFIED_DOCKET_MATCH
    assert attempts[0].linked_docket_id == linked.id


def test_attempt_auto_link_no_candidates_links_nothing(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Auto Link No Match Co")
    _seed_bankruptcy_evidence(
        db_session,
        issuer_id,
        excerpt="Auto Link No Match Co filed for chapter 11 bankruptcy protection.",
        as_of_date=date(2026, 7, 9),
    )

    result = court_docket_service.attempt_auto_link(
        db_session,
        None,  # type: ignore[arg-type]
        None,
        issuer_id=issuer_id,
        issuer_legal_name="Auto Link No Match Co",
        environment="test",
        search_dockets_fn=lambda db, http_client, *, query, court: [],
    )

    assert result.outcome is CourtDocketLinkMatchOutcome.CHECKED_NO_RELEVANT_DOCKET
    assert result.sync_result is None


def test_attempt_auto_link_ambiguous_candidates_link_nothing(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Ambiguous Match Co")
    _seed_bankruptcy_evidence(
        db_session,
        issuer_id,
        excerpt=(
            "Ambiguous Match Co filed case numbers 26-77777 and 26-88888 in "
            "connection with its chapter 11 proceedings."
        ),
        as_of_date=date(2026, 7, 9),
    )
    candidate_a = _search_candidate(
        db_session, docket_id=888002, case_name="Ambiguous Match Co A", docket_number="26-77777"
    )
    candidate_b = _search_candidate(
        db_session, docket_id=888003, case_name="Ambiguous Match Co B", docket_number="26-88888"
    )

    result = court_docket_service.attempt_auto_link(
        db_session,
        None,  # type: ignore[arg-type]
        None,
        issuer_id=issuer_id,
        issuer_legal_name="Ambiguous Match Co",
        environment="test",
        search_dockets_fn=lambda db, http_client, *, query, court: [candidate_a, candidate_b],
    )

    assert result.outcome is CourtDocketLinkMatchOutcome.AMBIGUOUS_MANUAL_REVIEW
    assert result.sync_result is None
    assert court_docket_repository.get_docket_by_courtlistener_id(db_session, 888002) is None
    assert court_docket_repository.get_docket_by_courtlistener_id(db_session, 888003) is None
