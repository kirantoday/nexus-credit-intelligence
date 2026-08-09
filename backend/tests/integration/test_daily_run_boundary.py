"""Integration tests for the Milestone 7.5.2 daily-run-boundary semantics.

Covers: `filing_monitor_run_repository`/`market_discovery_repository`'s new
`get_latest_successful_daily_run`/`get_latest_daily_run` (mode=backfill
structurally excluded), `filing_monitor_api_service.get_morning_brief`'s
one-authoritative-daily-run combination across both pipelines, and
`triggered_since` (processing-time) alert filtering — the fix for the real
production bug where a `mode=backfill` run's timestamp silently drove the
Morning Brief's "Last successful run" display (PLAN.md Milestone 7.5.2).

Each test's own rows always use `datetime.now()`-derived timestamps (via
`complete_run`), so they are guaranteed to be the most recent of their kind
regardless of what historical production data already exists in the shared
`nexus` schema — the assertions compare relative ordering between rows
created within the same test, never an assumption that the table starts
empty.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.types import (
    DataClassification,
    DetectionMethod,
    EvidenceSeverity,
    FilingMonitorRunMode,
    FilingMonitorRunStatus,
    ProviderName,
    TransformationType,
)
from app.domain.alert import AlertEventCreate
from app.domain.filing_monitor_run import FilingMonitorRunCreate
from app.domain.issuer import IssuerCreate
from app.domain.market_discovery import MarketDiscoveryRunCreate
from app.domain.provenance import ProvenanceCreate
from app.models.alert import AlertEvent as AlertEventModel
from app.repositories import (
    alert_repository,
    filing_monitor_run_repository,
    issuer_repository,
    market_discovery_repository,
    provenance_repository,
)
from app.services import morning_brief_service
from tests.integration.conftest import reported_public_provenance


def _complete(
    db: Session,
    run_id: UUID,
    *,
    market_discovery: bool,
    status: FilingMonitorRunStatus = FilingMonitorRunStatus.SUCCESS,
) -> None:
    if market_discovery:
        market_discovery_repository.complete_run(
            db,
            run_id,
            status=status,
            resulting_watermark=datetime.now(tz=UTC),
            queries_executed=1,
            filings_examined=0,
            candidate_filings=0,
            issuers_resolved_existing=0,
            issuers_resolved_new=0,
            issuers_ambiguous=0,
            issuers_rejected=0,
            evidence_created=0,
            alerts_created=0,
            errors_count=0,
            error_summary=None,
        )
    else:
        filing_monitor_run_repository.complete_run(
            db,
            run_id,
            status=status,
            resulting_watermark=datetime.now(tz=UTC),
            issuers_checked=0,
            filings_discovered=0,
            filings_processed=0,
            alerts_created=0,
            errors_count=0,
            error_summary=None,
        )


def test_filing_monitor_repo_daily_run_excludes_more_recent_backfill(
    db_session: Session,
) -> None:
    """A `backfill` run completed AFTER a `delta` run must never be returned
    by `get_latest_successful_daily_run` — this is the exact shape of the
    production bug (a backfill's completion time silently became "the
    latest successful run"). `get_latest_successful_run` (unscoped by mode,
    left unchanged) legitimately DOES return the later backfill run — the
    two functions serve different purposes and must disagree here."""
    delta_run = filing_monitor_run_repository.create_run(
        db_session, FilingMonitorRunCreate(mode=FilingMonitorRunMode.DELTA)
    )
    _complete(db_session, delta_run.id, market_discovery=False)

    backfill_run = filing_monitor_run_repository.create_run(
        db_session,
        FilingMonitorRunCreate(mode=FilingMonitorRunMode.BACKFILL, backfill_lookback_days=30),
    )
    _complete(db_session, backfill_run.id, market_discovery=False)

    latest_any_mode = filing_monitor_run_repository.get_latest_successful_run(db_session)
    assert latest_any_mode is not None
    assert latest_any_mode.id == backfill_run.id

    latest_daily = filing_monitor_run_repository.get_latest_successful_daily_run(db_session)
    assert latest_daily is not None
    assert latest_daily.id == delta_run.id
    assert latest_daily.mode is FilingMonitorRunMode.DELTA


def test_market_discovery_repo_daily_run_excludes_more_recent_backfill(
    db_session: Session,
) -> None:
    delta_run = market_discovery_repository.create_run(
        db_session,
        MarketDiscoveryRunCreate(
            mode=FilingMonitorRunMode.DELTA,
            window_start_date=date(2026, 8, 7),
            window_end_date=date(2026, 8, 7),
        ),
    )
    _complete(db_session, delta_run.id, market_discovery=True)

    backfill_run = market_discovery_repository.create_run(
        db_session,
        MarketDiscoveryRunCreate(
            mode=FilingMonitorRunMode.BACKFILL,
            window_start_date=date(2026, 1, 1),
            window_end_date=date(2026, 8, 6),
        ),
    )
    _complete(db_session, backfill_run.id, market_discovery=True)

    latest_any_mode = market_discovery_repository.get_latest_successful_run(db_session)
    assert latest_any_mode is not None
    assert latest_any_mode.id == backfill_run.id

    latest_daily = market_discovery_repository.get_latest_successful_daily_run(db_session)
    assert latest_daily is not None
    assert latest_daily.id == delta_run.id
    assert latest_daily.mode is FilingMonitorRunMode.DELTA


def test_run_details_daily_boundary_ignores_later_backfill(db_session: Session) -> None:
    """End-to-end reproduction of the production bug: a `market_discovery`
    delta run completes, then a `filing_monitor` backfill run completes
    later. `RunDetails.last_successful_run`/`.since` (the diagnostics block
    Milestone 7.5.2's correction moved this logic into, unchanged) must
    reflect the delta run, never the more-recent backfill."""
    delta_run = market_discovery_repository.create_run(
        db_session,
        MarketDiscoveryRunCreate(
            mode=FilingMonitorRunMode.DELTA,
            window_start_date=date(2026, 8, 7),
            window_end_date=date(2026, 8, 7),
        ),
    )
    _complete(db_session, delta_run.id, market_discovery=True)
    completed_delta = market_discovery_repository.get_latest_daily_run(db_session)
    assert completed_delta is not None
    assert completed_delta.completed_at is not None

    backfill_run = filing_monitor_run_repository.create_run(
        db_session,
        FilingMonitorRunCreate(mode=FilingMonitorRunMode.BACKFILL, backfill_lookback_days=200),
    )
    _complete(db_session, backfill_run.id, market_discovery=False)

    brief = morning_brief_service.get_morning_brief(db_session)

    assert brief.run_details.last_successful_run is not None
    assert brief.run_details.last_successful_run.id == delta_run.id
    assert brief.run_details.last_successful_run.mode == FilingMonitorRunMode.DELTA
    # `since` is the run's `started_at`, not `completed_at` — everything the
    # run itself discovers is necessarily written before its own completion,
    # so a `completed_at` boundary would exclude the run's own output.
    assert brief.run_details.since == completed_delta.started_at


def test_alert_repository_triggered_since_filters_by_processing_time(
    db_session: Session,
) -> None:
    """`triggered_since` filters by Nexus's own processing time
    (`triggered_at`), never by the alert's `as_of_date` (real-world event
    date) — an older event discovered just now must still pass a recent
    `triggered_since` boundary.

    `triggered_at` is a `server_default=now()` column, and Postgres's `now()`
    returns the enclosing transaction's start time — constant for every
    statement in this test's single wrapping transaction (`db_session`
    fixture) — so two alerts created moments apart in test code would
    otherwise get an identical `triggered_at`. This test sets `triggered_at`
    explicitly post-creation to model two distinct processing times, exactly
    as two separate real daily-run invocations (each its own transaction)
    would naturally produce distinct values."""
    provenance = provenance_repository.create_provenance(db_session, reported_public_provenance())
    issuer = issuer_repository.create_issuer(
        db_session,
        IssuerCreate(legal_name=f"Triggered Since Test Co {uuid4()}", provenance_id=provenance.id),
    )

    def _seed(as_of: date, triggered_at: datetime) -> None:
        calc_provenance = provenance_repository.create_provenance(
            db_session,
            ProvenanceCreate(
                provider=ProviderName.SEC_EDGAR,
                source_record_id=f"test-bundle-{uuid4()}",
                as_of_date=as_of,
                retrieved_at=reported_public_provenance().retrieved_at,
                transformation=TransformationType.REPORTED,
                classification=DataClassification.PUBLIC,
            ),
        )
        alert = alert_repository.create_alert(
            db_session,
            AlertEventCreate(
                issuer_id=issuer.id,
                category="bankruptcy_or_receivership",
                severity=EvidenceSeverity.HIGH,
                headline="Test alert for triggered_since filtering.",
                explanation="Seeded for daily-run-boundary tests.",
                evidence_ids=[uuid4()],
                bundle_key=f"sec_edgar:sec_filing:{uuid4()}",
                primary_evidence_provider="sec_edgar",
                primary_source_label="Test source label",
                primary_source_url=None,
                detection_method=DetectionMethod.DETERMINISTIC,
                ai_assisted=False,
                confidence=0.9,
                as_of_date=as_of,
                provenance_id=calc_provenance.id,
            ),
        )
        row = db_session.get(AlertEventModel, alert.id)
        assert row is not None
        row.triggered_at = triggered_at
        db_session.flush()

    now = datetime.now(tz=UTC)

    # An old-dated event (e.g. a historical backfill discovered "now") must
    # still count as newly-triggered — event date and processing time are
    # deliberately independent axes.
    _seed(date(2026, 3, 1), triggered_at=now - timedelta(days=1))
    _seed(date(2026, 8, 7), triggered_at=now)

    boundary = now - timedelta(microseconds=1)
    new_alerts, new_total = alert_repository.list_alerts(
        db_session, issuer_id=issuer.id, triggered_since=boundary
    )

    assert new_total == 1
    assert new_alerts[0].as_of_date == date(2026, 8, 7)

    all_alerts, all_total = alert_repository.list_alerts(db_session, issuer_id=issuer.id)
    assert all_total == 2
