"""Integration tests for `app/services/enrichment_orchestrator.py` against
the live nexus schema (PLAN.md Milestone 7.5).

No live provider network: passing `EnrichmentClients(sec=None,
courtlistener=None, openfigi=None)` deterministically routes every provider
through its "not configured" branch (`EnrichmentStatus.UNAVAILABLE`) —
enough to prove status persistence, per-provider isolation, and the
staleness-driven re-run/force behavior without needing live HTTP fakes for
three different providers. `test_enrichment_orchestrator_staleness.py`
covers `_should_run`'s full state-transition matrix in isolation.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.core.types import (
    DetectionMethod,
    EnrichmentStatus,
    EvidenceSeverity,
    EvidenceType,
    ProviderName,
)
from app.domain.issuer import IssuerCreate
from app.domain.research_evidence import ResearchEvidenceCreate
from app.providers.base.http_client import ThrottledHttpClient
from app.repositories import (
    alert_repository,
    issuer_enrichment_status_repository,
    issuer_repository,
    provenance_repository,
    research_evidence_repository,
)
from app.services.enrichment_orchestrator import EnrichmentClients, enrich_issuer
from app.services.filing_monitor_service import IssuerFilingProcessingResult
from tests.integration.conftest import reported_public_provenance

_NO_CLIENTS = EnrichmentClients(sec=None, courtlistener=None, openfigi=None)


def _seed_issuer(db: Session, *, legal_name: str, cik: str | None = None) -> UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    return issuer_repository.create_issuer(
        db, IssuerCreate(legal_name=legal_name, cik=cik, provenance_id=provenance.id)
    ).id


def test_never_checked_issuer_runs_every_provider_and_persists_status(db_session: Session) -> None:
    issuer_id = _seed_issuer(
        db_session, legal_name="Enrichment Orchestrator Test Co", cik="9880000001"
    )

    results = enrich_issuer(db_session, issuer_id, _NO_CLIENTS, None, environment="test")

    assert set(results.keys()) == {
        ProviderName.SEC_EDGAR,
        ProviderName.COURTLISTENER,
        ProviderName.OPENFIGI,
    }
    for status in results.values():
        assert status.status is EnrichmentStatus.UNAVAILABLE
        assert status.attempt_count == 1

    persisted = issuer_enrichment_status_repository.get_status(
        db_session, issuer_id=issuer_id, provider=ProviderName.SEC_EDGAR
    )
    assert persisted is not None
    assert persisted.status is EnrichmentStatus.UNAVAILABLE


def test_fresh_unavailable_status_is_not_immediately_rerun(db_session: Session) -> None:
    issuer_id = _seed_issuer(
        db_session, legal_name="Enrichment Freshness Test Co", cik="9880000002"
    )

    enrich_issuer(db_session, issuer_id, _NO_CLIENTS, None, environment="test")
    second_run = enrich_issuer(db_session, issuer_id, _NO_CLIENTS, None, environment="test")

    # Second run within the recheck TTL should return the *existing* status
    # rows (attempt_count still 1), not re-attempt them.
    for status in second_run.values():
        assert status.attempt_count == 1


def test_force_reruns_regardless_of_freshness(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, legal_name="Enrichment Force Test Co", cik="9880000003")

    enrich_issuer(db_session, issuer_id, _NO_CLIENTS, None, environment="test")
    forced = enrich_issuer(db_session, issuer_id, _NO_CLIENTS, None, environment="test", force=True)

    for status in forced.values():
        assert status.attempt_count == 2


def test_issuer_with_no_cik_marks_sec_unsupported_not_unavailable(db_session: Session) -> None:
    """`_enrich_sec` checks `http_client is None` before `cik is None` (no
    client at all means nothing can be checked, a stronger condition than
    "checked, but this issuer doesn't apply") — so this test supplies a
    non-`None` sentinel for the SEC client specifically to isolate the
    no-CIK path; `_enrich_sec` never actually calls a method on it before
    the CIK check short-circuits."""
    issuer_id = _seed_issuer(db_session, legal_name="No CIK Test Co", cik=None)
    clients = EnrichmentClients(sec=object(), courtlistener=None, openfigi=None)  # type: ignore[arg-type]

    results = enrich_issuer(db_session, issuer_id, clients, None, environment="test")

    assert results[ProviderName.SEC_EDGAR].status is EnrichmentStatus.UNSUPPORTED
    assert results[ProviderName.SEC_EDGAR].error_classification == "issuer_has_no_cik"


def test_unknown_issuer_raises(db_session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        enrich_issuer(db_session, UUID(int=0), _NO_CLIENTS, None, environment="test")


def test_sec_enrichment_evidence_synthesizes_alerts(db_session: Session) -> None:
    """Regression test for a real bug found during Milestone 7.5 live pilot
    recovery: `_enrich_sec`'s own historical-lookback SEC re-check was
    creating real `research_evidence` rows that never flowed into
    `alert_synthesis_service`, unlike discovery-triggered evidence — an
    issuer's enrichment-discovered distress signal would silently never
    become an alert. Fixed by threading the same alert-synthesis +
    universe-classification calls through `_enrich_sec` that
    `market_discovery_service` already uses."""
    issuer_id = _seed_issuer(
        db_session, legal_name="Enrichment Alert Synthesis Test Co", cik="9880000004"
    )
    evidence_provenance = provenance_repository.create_provenance(
        db_session, reported_public_provenance()
    )
    evidence = research_evidence_repository.create_evidence(
        db_session,
        ResearchEvidenceCreate(
            issuer_id=issuer_id,
            evidence_provider=ProviderName.SEC_EDGAR.value,
            source_type="sec_filing",
            evidence_type=EvidenceType.GOING_CONCERN,
            severity=EvidenceSeverity.HIGH,
            matched_rule="phrase_substantial_doubt_going_concern",
            evidence_excerpt="Substantial doubt about ability to continue as a going concern.",
            confidence=0.9,
            detection_method=DetectionMethod.DETERMINISTIC,
            provenance_id=evidence_provenance.id,
        ),
    )

    def _fake_process_issuer_filings(
        db: Session,
        http_client: ThrottledHttpClient,
        *,
        cik: str,
        issuer_id: UUID,
        since_date: date | None,
    ) -> IssuerFilingProcessingResult:
        return IssuerFilingProcessingResult(
            filings_discovered=1, filings_processed=1, evidence=[evidence]
        )

    clients = EnrichmentClients(sec=object(), courtlistener=None, openfigi=None)  # type: ignore[arg-type]

    results = enrich_issuer(
        db_session,
        issuer_id,
        clients,
        None,
        environment="test",
        process_issuer_filings_fn=_fake_process_issuer_filings,
    )

    assert results[ProviderName.SEC_EDGAR].status is EnrichmentStatus.COMPLETE
    alerts, total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert total == 1
    assert alerts[0].primary_evidence_provider == ProviderName.SEC_EDGAR.value
