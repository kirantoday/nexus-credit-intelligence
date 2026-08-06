"""Integration tests for `app/services/filing_monitor_service.py` (PLAN.md 24.5).

Runs against the live `nexus` schema (rolled back after each test — see
`join_transaction_mode="create_savepoint"` in `conftest.py`, needed because
this service manages its own commit boundaries). No live SEC network: real
fetch/text functions are replaced with fakes matching the same Protocol, so
watermark/idempotency/retry logic is proven without hitting data.sec.gov.

`run_monitor` targets *every* issuer in a `research_universe`/`benchmark`
collection system-wide, by design — not just this test's own seeded issuer.
Since real, permanently-committed Research Universes now exist (the
Milestone 6.5 seed script, `app/scripts/seed_research_universes.py`), every
fake `fetch_filings_fn`/`fetch_filing_text_fn` below is CIK-aware: it only
produces data for the test's own CIK and returns nothing for every other
real issuer in scope, exactly like the real data.sec.gov would for a CIK it
has no matching data for. Assertions on `issuers_checked` are `>=` rather
than `==` for the same reason — this run's population legitimately includes
every real seeded issuer, not just this test's one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.core.types import (
    CollectionPriority,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    ProviderName,
    VerificationStatus,
)
from app.domain.collection import CollectionCreate, CollectionMembershipCreate
from app.domain.issuer import IssuerCreate
from app.domain.sec_filing import SecFiling, SecFilingCreate
from app.providers.base import raw_payload_store
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar.provider import FilingIngestResult, FilingTextResult
from app.repositories import (
    alert_repository,
    collection_repository,
    filing_monitor_run_repository,
    issuer_repository,
    provenance_repository,
    research_evidence_repository,
    sec_filing_repository,
)
from app.services import filing_monitor_service
from tests.integration.conftest import reported_public_provenance

_CLEAN_TEXT = "Revenue increased 12% year over year. No unusual items to report."
_BANKRUPTCY_TEXT = (
    "On August 5, 2026, the Company filed voluntary petitions for relief "
    "under chapter 11 of the United States Bankruptcy Code."
)


def _seed_issuer(db: Session, *, cik: str = "9999901001") -> UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    issuer = issuer_repository.create_issuer(
        db,
        IssuerCreate(
            legal_name="Filing Monitor Test Co",
            cik=cik,
            lei=None,
            ticker="FMTC",
            sic="9999",
            sector=None,
            provenance_id=provenance.id,
        ),
    )
    return issuer.id


def _seed_research_universe(db: Session, issuer_id: UUID) -> None:
    collection = collection_repository.create_collection(
        db,
        CollectionCreate(
            slug=f"test-universe-{issuer_id}",
            name="Test Research Universe",
            description="Seeded for filing_monitor_service integration tests.",
            collection_type=CollectionType.RESEARCH_UNIVERSE,
            scope=CollectionScope.ORGANIZATION,
            visibility=CollectionVisibility.PUBLIC,
            curation_method=CurationMethod.SYSTEM_SEEDED,
            verification_status=VerificationStatus.VERIFIED,
            priority=CollectionPriority.HIGH,
        ),
    )
    collection_repository.add_membership(
        db,
        CollectionMembershipCreate(
            collection_id=collection.id,
            issuer_id=issuer_id,
            rationale="Seeded for a filing_monitor_service integration test.",
            verification_status=VerificationStatus.VERIFIED,
            added_by="test_suite",
        ),
    )


def _fake_filing(db: Session, issuer_id: UUID, *, accession_no: str, text: str) -> SecFiling:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    filing, _created = sec_filing_repository.create_filing(
        db,
        SecFilingCreate(
            issuer_id=issuer_id,
            accession_no=accession_no,
            form_type="8-K",
            filing_date=date.today(),
            is_amendment=False,
            primary_document="test-filing.htm",
            primary_document_url=f"https://example.invalid/{accession_no}.htm",
            provenance_id=provenance.id,
        ),
    )
    return filing


def _http_client() -> ThrottledHttpClient:
    return ThrottledHttpClient(user_agent="filing-monitor-tests")


def _fake_text_result(db: Session, text: str) -> FilingTextResult:
    """A real `raw_provider_payload` row (needed since
    `filing_monitor_service` links a provenance back to it), with fake
    document bytes — no network."""
    payload = raw_payload_store.store_raw_payload(
        db,
        provider=ProviderName.SEC_EDGAR,
        source_record_id="fake-accession",
        url="https://example.invalid/fake-filing.htm",
        raw_bytes=text.encode("utf-8"),
        payload_json={"extracted_text": text},
        content_type="text/html",
        retrieved_at=datetime.now(UTC),
    )
    return FilingTextResult(
        text=text,
        raw_payload_id=payload.id,
        source_url="https://example.invalid/fake-filing.htm",
        retrieved_at=payload.retrieved_at,
    )


def test_baseline_mode_ingests_no_filings_and_establishes_watermark(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session)
    _seed_research_universe(db_session, issuer_id)

    def fetch_filings_fn(*args: object, **kwargs: object) -> list[FilingIngestResult]:
        pytest.fail("baseline mode must never call the filing-fetch function")

    def fetch_text_fn(*args: object, **kwargs: object) -> FilingTextResult:
        pytest.fail("baseline mode must never call the filing-text function")

    run = filing_monitor_service.run_monitor(
        db_session,
        _http_client(),
        None,
        mode=FilingMonitorRunMode.BASELINE,
        environment="test",
        fetch_filings_fn=fetch_filings_fn,
        fetch_filing_text_fn=fetch_text_fn,
    )

    assert run.status is FilingMonitorRunStatus.BASELINE_ESTABLISHED
    assert run.filings_discovered == 0
    assert run.resulting_watermark is not None
    # >= not == : this run's target population is every real issuer in a
    # research_universe/benchmark collection system-wide, not just this
    # test's own — see module docstring.
    assert run.issuers_checked >= 1


def test_delta_mode_creates_evidence_and_alert_for_bankruptcy_filing(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, cik="9999901002")
    _seed_research_universe(db_session, issuer_id)

    def fetch_filings_fn(
        db: Session, http_client: object, *, cik: str, forms: object, since: object
    ) -> list[FilingIngestResult]:
        if cik != "9999901002":
            return []
        filing = _fake_filing(
            db, issuer_id, accession_no="9999901002-26-000001", text=_BANKRUPTCY_TEXT
        )
        return [FilingIngestResult(filing=filing, filing_created=True, item_codes="1.03")]

    def fetch_text_fn(
        db: Session, http_client: object, *, cik: str, filing: SecFiling
    ) -> FilingTextResult:
        return _fake_text_result(db, _BANKRUPTCY_TEXT)

    run = filing_monitor_service.run_monitor(
        db_session,
        _http_client(),
        None,
        mode=FilingMonitorRunMode.DELTA,
        environment="test",
        fetch_filings_fn=fetch_filings_fn,  # type: ignore[arg-type]
        fetch_filing_text_fn=fetch_text_fn,  # type: ignore[arg-type]
    )

    assert run.status is FilingMonitorRunStatus.SUCCESS
    assert run.filings_discovered == 1
    assert run.filings_processed == 1
    assert run.alerts_created == 1
    assert run.errors_count == 0
    assert run.resulting_watermark is not None

    evidence = research_evidence_repository.list_evidence(db_session, issuer_id=issuer_id)
    assert len(evidence) >= 1
    assert any(e.matched_rule == "8k_item_1_03_bankruptcy" for e in evidence)

    alerts, total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert total == 1
    assert alerts[0].ai_assisted is False
    assert alerts[0].detection_method.value == "deterministic"
    assert "Potential" in alerts[0].headline


def test_clean_filing_produces_no_evidence_or_alert(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, cik="9999901003")
    _seed_research_universe(db_session, issuer_id)

    def fetch_filings_fn(
        db: Session, http_client: object, *, cik: str, forms: object, since: object
    ) -> list[FilingIngestResult]:
        if cik != "9999901003":
            return []
        filing = _fake_filing(db, issuer_id, accession_no="9999901003-26-000001", text=_CLEAN_TEXT)
        return [FilingIngestResult(filing=filing, filing_created=True, item_codes=None)]

    def fetch_text_fn(
        db: Session, http_client: object, *, cik: str, filing: SecFiling
    ) -> FilingTextResult:
        return _fake_text_result(db, _CLEAN_TEXT)

    run = filing_monitor_service.run_monitor(
        db_session,
        _http_client(),
        None,
        mode=FilingMonitorRunMode.DELTA,
        environment="test",
        fetch_filings_fn=fetch_filings_fn,  # type: ignore[arg-type]
        fetch_filing_text_fn=fetch_text_fn,  # type: ignore[arg-type]
    )

    assert run.status is FilingMonitorRunStatus.SUCCESS
    alerts, total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert total == 0


def test_idempotent_rerun_does_not_duplicate_evidence_or_alerts(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, cik="9999901004")
    _seed_research_universe(db_session, issuer_id)
    accession_no = "9999901004-26-000001"

    call_count = {"filings": 0}

    def fetch_filings_fn(
        db: Session, http_client: object, *, cik: str, forms: object, since: object
    ) -> list[FilingIngestResult]:
        if cik != "9999901004":
            return []
        call_count["filings"] += 1
        filing, created = sec_filing_repository.create_filing(
            db,
            SecFilingCreate(
                issuer_id=issuer_id,
                accession_no=accession_no,
                form_type="8-K",
                filing_date=date.today(),
                is_amendment=False,
                primary_document="test-filing.htm",
                primary_document_url="https://example.invalid/x.htm",
                provenance_id=provenance_repository.create_provenance(
                    db, reported_public_provenance()
                ).id,
            ),
        )
        return [FilingIngestResult(filing=filing, filing_created=created, item_codes="1.03")]

    def fetch_text_fn(
        db: Session, http_client: object, *, cik: str, filing: SecFiling
    ) -> FilingTextResult:
        return _fake_text_result(db, _BANKRUPTCY_TEXT)

    filing_monitor_service.run_monitor(
        db_session,
        _http_client(),
        None,
        mode=FilingMonitorRunMode.DELTA,
        environment="test",
        fetch_filings_fn=fetch_filings_fn,  # type: ignore[arg-type]
        fetch_filing_text_fn=fetch_text_fn,  # type: ignore[arg-type]
    )
    evidence_after_first_run = research_evidence_repository.list_evidence(
        db_session, issuer_id=issuer_id
    )
    # The bankruptcy text genuinely matches two rules (the 8-K Item 1.03
    # item-code rule and the "voluntary petition ... chapter 11" phrase
    # rule) — both are real, distinct evidence, not a duplication bug.
    assert len(evidence_after_first_run) == 2

    filing_monitor_service.run_monitor(
        db_session,
        _http_client(),
        None,
        mode=FilingMonitorRunMode.DELTA,
        environment="test",
        fetch_filings_fn=fetch_filings_fn,  # type: ignore[arg-type]
        fetch_filing_text_fn=fetch_text_fn,  # type: ignore[arg-type]
    )
    evidence_after_second_run = research_evidence_repository.list_evidence(
        db_session, issuer_id=issuer_id
    )
    assert len(evidence_after_second_run) == len(
        evidence_after_first_run
    ), "re-running must not duplicate evidence for the same filing"
    assert {e.id for e in evidence_after_second_run} == {e.id for e in evidence_after_first_run}

    _alerts, total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert total == 1, "re-running must not duplicate the alert for the same evidence bundle"
    assert call_count["filings"] == 2, "the fetch function itself is still called each run"


def test_failed_issuer_does_not_advance_watermark_and_records_error(
    db_session: Session,
) -> None:
    issuer_id = _seed_issuer(db_session, cik="9999901005")
    _seed_research_universe(db_session, issuer_id)

    # Captured rather than assumed `None`: other real, permanently-committed
    # runs (e.g. a real baseline run against the live database) may already
    # exist outside this test's own transaction, so "the watermark must not
    # advance" is proven by equality to whatever it was *before* this run,
    # not by a hardcoded `None`.
    watermark_before = filing_monitor_run_repository.get_latest_successful_run(db_session)
    previous_watermark = watermark_before.resulting_watermark if watermark_before else None

    def failing_fetch_filings_fn(
        db: Session, http_client: object, *, cik: str, forms: object, since: object
    ) -> list[FilingIngestResult]:
        if cik != "9999901005":
            return []
        raise ConnectionError("simulated SEC EDGAR outage")

    def fetch_text_fn(
        db: Session, http_client: object, *, cik: str, filing: SecFiling
    ) -> FilingTextResult:
        pytest.fail("must not be called when filing discovery itself fails")

    run = filing_monitor_service.run_monitor(
        db_session,
        _http_client(),
        None,
        mode=FilingMonitorRunMode.DELTA,
        environment="test",
        fetch_filings_fn=failing_fetch_filings_fn,  # type: ignore[arg-type]
        fetch_filing_text_fn=fetch_text_fn,  # type: ignore[arg-type]
    )

    assert run.status is FilingMonitorRunStatus.COMPLETED_WITH_ERRORS
    assert run.errors_count == 1
    assert (
        run.resulting_watermark == previous_watermark
    ), "a run with errors must not advance the watermark"
    assert run.error_summary is not None
    assert "simulated SEC EDGAR outage" in run.error_summary
    assert "CIK 9999901005" in run.error_summary


def test_backfill_mode_marks_run_and_alerts_as_backfill(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, cik="9999901006")
    _seed_research_universe(db_session, issuer_id)

    def fetch_filings_fn(
        db: Session, http_client: object, *, cik: str, forms: object, since: object
    ) -> list[FilingIngestResult]:
        assert since == date.today() - timedelta(days=30)
        if cik != "9999901006":
            return []
        filing = _fake_filing(
            db, issuer_id, accession_no="9999901006-26-000001", text=_BANKRUPTCY_TEXT
        )
        return [FilingIngestResult(filing=filing, filing_created=True, item_codes="1.03")]

    def fetch_text_fn(
        db: Session, http_client: object, *, cik: str, filing: SecFiling
    ) -> FilingTextResult:
        return _fake_text_result(db, _BANKRUPTCY_TEXT)

    run = filing_monitor_service.run_monitor(
        db_session,
        _http_client(),
        None,
        mode=FilingMonitorRunMode.BACKFILL,
        backfill_days=30,
        environment="test",
        fetch_filings_fn=fetch_filings_fn,  # type: ignore[arg-type]
        fetch_filing_text_fn=fetch_text_fn,  # type: ignore[arg-type]
    )

    assert run.is_backfill is True
    assert run.status is FilingMonitorRunStatus.SUCCESS

    alerts, _total = alert_repository.list_alerts(db_session, issuer_id=issuer_id)
    assert len(alerts) == 1
    assert alerts[0].is_backfill is True


def test_backfill_mode_requires_backfill_days(db_session: Session) -> None:
    with pytest.raises(ValueError, match="backfill_days"):
        filing_monitor_service.run_monitor(
            db_session,
            _http_client(),
            None,
            mode=FilingMonitorRunMode.BACKFILL,
            environment="test",
        )
