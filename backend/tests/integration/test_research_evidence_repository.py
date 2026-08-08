"""Integration tests for `app/repositories/research_evidence_repository.py`
functions added for Milestone 7.5.1's reconciliation script.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.types import DetectionMethod, EvidenceSeverity, EvidenceType, ProviderName
from app.domain.issuer import IssuerCreate
from app.domain.research_evidence import ResearchEvidenceCreate
from app.repositories import issuer_repository, provenance_repository, research_evidence_repository
from tests.integration.conftest import reported_public_provenance


def _seed_issuer(db: Session, *, legal_name: str) -> UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, provenance_id=provenance.id)
    ).id


def _evidence(db: Session, issuer_id: UUID, *, evidence_type: EvidenceType) -> None:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    research_evidence_repository.create_evidence(
        db,
        ResearchEvidenceCreate(
            issuer_id=issuer_id,
            evidence_provider=ProviderName.SEC_EDGAR.value,
            source_type="sec_filing",
            evidence_type=evidence_type,
            severity=EvidenceSeverity.HIGH,
            matched_rule="test_rule",
            evidence_excerpt="Test excerpt.",
            confidence=0.9,
            detection_method=DetectionMethod.DETERMINISTIC,
            provenance_id=provenance.id,
        ),
    )


def test_list_evidence_by_issuer_and_types_filters_correctly(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Evidence Repo Test Co")
    other_issuer_id = _seed_issuer(db_session, legal_name="Evidence Repo Other Test Co")
    _evidence(db_session, issuer_id, evidence_type=EvidenceType.CHAPTER_11)
    _evidence(db_session, issuer_id, evidence_type=EvidenceType.SUBSTANTIAL_DOUBT)
    _evidence(db_session, issuer_id, evidence_type=EvidenceType.WORKFORCE_REDUCTION)
    _evidence(db_session, other_issuer_id, evidence_type=EvidenceType.CHAPTER_11)

    result = research_evidence_repository.list_evidence_by_issuer_and_types(
        db_session, issuer_id, [EvidenceType.CHAPTER_11, EvidenceType.SUBSTANTIAL_DOUBT]
    )

    assert {e.evidence_type for e in result} == {
        EvidenceType.CHAPTER_11,
        EvidenceType.SUBSTANTIAL_DOUBT,
    }
    assert all(e.issuer_id == issuer_id for e in result)


def test_list_issuer_ids_with_evidence_types_finds_distinct_issuers(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Distinct Issuer Ids Test Co")
    _evidence(db_session, issuer_id, evidence_type=EvidenceType.CHAPTER_11)
    _evidence(db_session, issuer_id, evidence_type=EvidenceType.CHAPTER_11)  # 2nd row, same issuer

    result = research_evidence_repository.list_issuer_ids_with_evidence_types(
        db_session, [EvidenceType.CHAPTER_11]
    )

    assert result.count(issuer_id) == 1
