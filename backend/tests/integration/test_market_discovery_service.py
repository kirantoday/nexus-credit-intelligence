"""Integration tests for `app/services/market_discovery_service.py`
(PLAN.md Milestone 7.5).

Runs against the live `nexus` schema (rolled back after each test). No live
SEC network: `search_full_text_fn`, `resolve_issuer_fn`, and
`process_issuer_filings_fn` are replaced with fakes matching the same
Protocols `market_discovery_service` defines, so Layer-0 query iteration,
issuer-identity-outcome handling, idempotency, and watermark behavior are
proven without hitting efts.sec.gov/data.sec.gov — mirroring
`test_filing_monitor_service.py`'s established fake-injection pattern.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.core.issuer_resolver import IssuerResolutionResult
from app.core.types import FilingMonitorRunMode, MarketDiscoveryResolutionOutcome
from app.domain.issuer import IssuerCreate
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.sec_edgar.client import FetchResult
from app.providers.sec_edgar.dto import SecFullTextSearchResponseDTO
from app.repositories import issuer_repository, market_discovery_repository, provenance_repository
from app.services import market_discovery_service
from app.services.enrichment_orchestrator import EnrichmentClients
from app.services.filing_monitor_service import IssuerFilingProcessingResult
from tests.integration.conftest import reported_public_provenance


def _fts_response(
    *hits: dict[str, object], total: int | None = None
) -> SecFullTextSearchResponseDTO:
    payload = {
        "hits": {
            "total": {"value": total if total is not None else len(hits), "relation": "eq"},
            "hits": [{"_id": f"{h['adsh']}:doc.htm", "_source": h} for h in hits],
        }
    }
    return SecFullTextSearchResponseDTO.model_validate(payload)


def _hit(*, cik: str = "9990000001", adsh: str = "0001-26-000001", form: str = "8-K") -> dict:
    return {
        "ciks": [cik],
        "display_names": [f"TEST CO (CIK {cik})"],
        "root_forms": [form],
        "file_date": "2026-07-05",
        "form": form,
        "adsh": adsh,
        "items": ["1.03"],
    }


def _fake_search_returning(
    *responses: SecFullTextSearchResponseDTO,
) -> market_discovery_service.SearchFullTextFn:
    """One response per call, in order — enough calls to exhaust `responses`
    then an empty response for any further calls (bounds the pagination
    loop safely even if a test only cares about the first page)."""
    calls = list(responses)

    def _fn(
        http_client: ThrottledHttpClient,
        *,
        query: str,
        forms: tuple[str, ...],
        start_date: date,
        end_date: date,
        from_offset: int,
        size: int,
    ) -> FetchResult[SecFullTextSearchResponseDTO]:
        dto = calls.pop(0) if calls else _fts_response()
        return FetchResult(
            dto=dto,
            raw_bytes=b"{}",
            content_type="application/json",
            url="https://efts.sec.gov/LATEST/search-index?q=test",
            retrieved_at=datetime.now(UTC),
        )

    return _fn


def _seed_issuer(db: Session, *, cik: str = "9990000001") -> UUID:
    provenance = provenance_repository.create_provenance(db, reported_public_provenance())
    issuer = issuer_repository.create_issuer(
        db,
        IssuerCreate(
            legal_name="Market Discovery Test Co",
            cik=cik,
            lei=None,
            ticker="MDTC",
            sic="9999",
            sector=None,
            provenance_id=provenance.id,
        ),
    )
    return issuer.id


def _no_op_process_issuer_filings(
    db: Session,
    http_client: ThrottledHttpClient,
    *,
    cik: str,
    issuer_id: UUID,
    since_date: date | None,
) -> IssuerFilingProcessingResult:
    return IssuerFilingProcessingResult(filings_discovered=0, filings_processed=0, evidence=[])


class _NullHttpClient:
    """Never actually called — every seam in these tests is faked — but a
    real `ThrottledHttpClient` isn't constructed to avoid requiring
    SEC_USER_AGENT in unit-style integration tests."""


def test_baseline_mode_establishes_watermark_without_processing(db_session: Session) -> None:
    run = market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        mode=FilingMonitorRunMode.BASELINE,
        environment="test",
        search_full_text_fn=_fake_search_returning(),
    )

    assert run.status.value == "baseline_established"
    assert run.queries_executed == 0
    assert run.resulting_watermark is not None


def test_backfill_requires_explicit_window(db_session: Session) -> None:
    with pytest.raises(ValueError, match="window_start"):
        market_discovery_service.run_discovery(
            db_session,
            _NullHttpClient(),  # type: ignore[arg-type]
            None,
            mode=FilingMonitorRunMode.BACKFILL,
            environment="test",
        )


def test_matched_existing_issuer_is_counted_and_processed(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, cik="9990000002")
    db_session.commit()

    def _resolve(
        db: Session, http_client: ThrottledHttpClient, *, cik: str
    ) -> IssuerResolutionResult:
        return IssuerResolutionResult(
            outcome=MarketDiscoveryResolutionOutcome.MATCHED_EXISTING,
            cik=cik,
            issuer_id=str(issuer_id),
            legal_name="Market Discovery Test Co",
            reason="issuer already known by CIK",
        )

    run = market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        mode=FilingMonitorRunMode.BACKFILL,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 6),
        environment="test",
        queries=("test phrase",),
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000002", adsh="0001-26-000002"))
        ),
        resolve_issuer_fn=_resolve,
        process_issuer_filings_fn=_no_op_process_issuer_filings,
    )

    assert run.status.value == "success"
    assert run.candidate_filings == 1
    assert run.issuers_resolved_existing == 1
    assert run.issuers_resolved_new == 0

    candidate = market_discovery_repository.get_candidate_by_filing(
        db_session, cik="9990000002", accession_no="0001-26-000002"
    )
    assert candidate is not None
    assert candidate.resolution_outcome == MarketDiscoveryResolutionOutcome.MATCHED_EXISTING
    assert candidate.issuer_id == issuer_id


def test_resolved_issuer_automatically_enters_enrichment_pipeline(db_session: Session) -> None:
    """PLAN.md Milestone 7.5: every resolved issuer — `matched_existing`
    included, not just `verified_new` — automatically flows into the
    reusable enrichment orchestrator once `enrichment_clients` is supplied,
    with no separate 'now go run CourtListener/OpenFIGI' step required."""
    issuer_id = _seed_issuer(db_session, cik="9990000006")
    db_session.commit()

    enrich_calls: list[UUID] = []

    def _fake_enrich_issuer(
        db: Session,
        called_issuer_id: UUID,
        clients: object,
        llm: object,
        *,
        environment: str,
        force: bool,
    ) -> dict[str, str]:
        enrich_calls.append(called_issuer_id)
        return {}

    def _resolve(
        db: Session, http_client: ThrottledHttpClient, *, cik: str
    ) -> IssuerResolutionResult:
        return IssuerResolutionResult(
            outcome=MarketDiscoveryResolutionOutcome.MATCHED_EXISTING,
            cik=cik,
            issuer_id=str(issuer_id),
            legal_name="Market Discovery Test Co",
            reason="issuer already known by CIK",
        )

    market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        mode=FilingMonitorRunMode.BACKFILL,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 6),
        environment="test",
        queries=("test phrase",),
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000006", adsh="0001-26-000006"))
        ),
        resolve_issuer_fn=_resolve,
        process_issuer_filings_fn=_no_op_process_issuer_filings,
        enrichment_clients=EnrichmentClients(sec=None, courtlistener=None, openfigi=None),
        enrich_issuer_fn=_fake_enrich_issuer,  # type: ignore[arg-type]
    )

    assert enrich_calls == [issuer_id]


def test_enrichment_is_skipped_when_no_clients_configured(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, cik="9990000007")
    db_session.commit()

    def _resolve(
        db: Session, http_client: ThrottledHttpClient, *, cik: str
    ) -> IssuerResolutionResult:
        return IssuerResolutionResult(
            outcome=MarketDiscoveryResolutionOutcome.VERIFIED_NEW,
            cik=cik,
            issuer_id=str(issuer_id),
            legal_name="Market Discovery Test Co",
            reason="verified live",
        )

    def _fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError(
            "enrich_issuer_fn should not be called when enrichment_clients is None"
        )

    run = market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        mode=FilingMonitorRunMode.BACKFILL,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 6),
        environment="test",
        queries=("test phrase",),
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000007", adsh="0001-26-000007"))
        ),
        resolve_issuer_fn=_resolve,
        process_issuer_filings_fn=_no_op_process_issuer_filings,
        enrich_issuer_fn=_fail_if_called,
    )

    assert run.status.value == "success"


def test_ambiguous_and_rejected_outcomes_never_trigger_filing_processing(
    db_session: Session,
) -> None:
    process_calls: list[str] = []

    def _track_process(
        db: Session,
        http_client: ThrottledHttpClient,
        *,
        cik: str,
        issuer_id: UUID,
        since_date: date | None,
    ) -> IssuerFilingProcessingResult:
        process_calls.append(cik)
        return IssuerFilingProcessingResult(filings_discovered=0, filings_processed=0, evidence=[])

    def _resolve_ambiguous(
        db: Session, http_client: ThrottledHttpClient, *, cik: str
    ) -> IssuerResolutionResult:
        return IssuerResolutionResult(
            outcome=MarketDiscoveryResolutionOutcome.AMBIGUOUS,
            cik=cik,
            issuer_id=None,
            legal_name=None,
            reason="ambiguous name match (2 candidates) — excluded, no automatic fuzzy merge",
        )

    run = market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        mode=FilingMonitorRunMode.BACKFILL,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 6),
        environment="test",
        queries=("test phrase",),
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000003", adsh="0001-26-000003"))
        ),
        resolve_issuer_fn=_resolve_ambiguous,
        process_issuer_filings_fn=_track_process,
    )

    assert run.issuers_ambiguous == 1
    assert run.issuers_resolved_existing == 0
    assert run.issuers_resolved_new == 0
    assert process_calls == []

    candidate = market_discovery_repository.get_candidate_by_filing(
        db_session, cik="9990000003", accession_no="0001-26-000003"
    )
    assert candidate is not None
    assert candidate.resolution_outcome == MarketDiscoveryResolutionOutcome.AMBIGUOUS
    assert candidate.issuer_id is None


def test_already_examined_filing_is_skipped_unless_forced(db_session: Session) -> None:
    issuer_id = _seed_issuer(db_session, cik="9990000004")
    db_session.commit()

    resolve_calls: list[str] = []

    def _resolve(
        db: Session, http_client: ThrottledHttpClient, *, cik: str
    ) -> IssuerResolutionResult:
        resolve_calls.append(cik)
        return IssuerResolutionResult(
            outcome=MarketDiscoveryResolutionOutcome.MATCHED_EXISTING,
            cik=cik,
            issuer_id=str(issuer_id),
            legal_name="Market Discovery Test Co",
            reason="issuer already known by CIK",
        )

    kwargs = dict(
        mode=FilingMonitorRunMode.BACKFILL,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 6),
        environment="test",
        queries=("test phrase",),
        resolve_issuer_fn=_resolve,
        process_issuer_filings_fn=_no_op_process_issuer_filings,
    )

    market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000004", adsh="0001-26-000004"))
        ),
        **kwargs,  # type: ignore[arg-type]
    )
    assert resolve_calls == ["9990000004"]

    # Second run, same (cik, accession_no), same rule_version: never
    # re-resolved — the whole point of `market_discovery_candidate` being
    # keyed on source identity, not on "have I ever looked at this."
    market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000004", adsh="0001-26-000004"))
        ),
        **kwargs,  # type: ignore[arg-type]
    )
    assert resolve_calls == ["9990000004"]

    # `force_reprocess=True` deliberately re-examines it — identity is
    # never "permanently closed" (PLAN.md Milestone 7.5).
    market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        force_reprocess=True,
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000004", adsh="0001-26-000004"))
        ),
        **kwargs,  # type: ignore[arg-type]
    )
    assert resolve_calls == ["9990000004", "9990000004"]


def test_watermark_only_advances_on_zero_errors(db_session: Session) -> None:
    """The actual invariant under test is "a run with errors leaves the
    watermark exactly where it was," not "the watermark is None" — this
    project's live shared `market_discovery_run` table may already have
    real prior successful runs (from genuine pilot/backfill activity) by
    the time this test runs, so asserting a specific `None` value would be
    testing an accident of an empty table, not the real rule."""

    def _failing_resolve(
        db: Session, http_client: ThrottledHttpClient, *, cik: str
    ) -> IssuerResolutionResult:
        raise RuntimeError("simulated live-fetch failure")

    previous = market_discovery_repository.get_latest_successful_run(db_session)
    expected_watermark = previous.resulting_watermark if previous else None

    run = market_discovery_service.run_discovery(
        db_session,
        _NullHttpClient(),  # type: ignore[arg-type]
        None,
        mode=FilingMonitorRunMode.BACKFILL,
        window_start=date(2026, 7, 1),
        window_end=date(2026, 7, 6),
        environment="test",
        queries=("test phrase",),
        search_full_text_fn=_fake_search_returning(
            _fts_response(_hit(cik="9990000005", adsh="0001-26-000005"))
        ),
        resolve_issuer_fn=_failing_resolve,
        process_issuer_filings_fn=_no_op_process_issuer_filings,
    )

    assert run.status.value == "completed_with_errors"
    assert run.errors_count == 1
    assert run.resulting_watermark == expected_watermark
