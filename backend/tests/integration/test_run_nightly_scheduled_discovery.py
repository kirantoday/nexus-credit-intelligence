"""Integration coverage for `app.scripts.run_nightly_scheduled_discovery.main`
— proves the wrapper correctly combines a real `market_discovery_run` row
(via the same `get_latest_successful_daily_run` the Morning Brief itself
uses) with the pure `should_run` decision, and launches the underlying
`run_market_discovery --mode delta` subprocess exactly once when — and
only when — it should. `subprocess.run` is stubbed (this test must never
make a real Anthropic/SEC call or spawn a real child process); the DB
session is the fixture's real, transactional, rolled-back-on-teardown
session (same pattern as `test_daily_run_boundary.py`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.domain.fred import FredObservation, FredSeriesRegistry
from app.domain.market_discovery import MarketDiscoveryRunCreate
from app.providers.fred.provider import FredSyncResult, ObservationSyncResult
from app.repositories import market_discovery_repository
from app.scripts import run_nightly_scheduled_discovery as wrapper


def _complete_delta_run(db: Session, *, window_start: date) -> None:
    run = market_discovery_repository.create_run(
        db,
        MarketDiscoveryRunCreate(
            mode=FilingMonitorRunMode.DELTA,
            window_start_date=window_start,
            window_end_date=window_start,
        ),
    )
    market_discovery_repository.complete_run(
        db,
        run.id,
        status=FilingMonitorRunStatus.SUCCESS,
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


@pytest.fixture
def _no_close_session(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Session:
    """`main()` calls `SessionLocal()` then `db.close()` in a `finally` —
    point it at this test's real transactional fixture session instead of
    opening a second, unrelated production connection. Closing the fixture
    session early is harmless (SQLAlchemy `Session.close()` is idempotent);
    the fixture's own teardown still rolls back everything unconditionally.

    Also stubs `_refresh_market_context` to a no-op by default — it makes a
    real FRED HTTP call otherwise, which no test in this module (other than
    the two dedicated FRED-refresh tests below, which restore the real
    function under a mocked `fred_provider.sync_series`) should ever do.
    """
    monkeypatch.setattr(wrapper, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(wrapper, "_refresh_market_context", lambda *a, **kw: None)
    return db_session


def test_valid_invocation_launches_exactly_one_delta_run(
    _no_close_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uses a date far enough in the future (2030) that no real production
    daily run could already exist for it — this project's live shared
    `market_discovery_run` table has real rows from genuine operation
    (including the 2026-08-10 daily cycle itself), so a near-term date
    would risk colliding with real data, same caution as
    `test_daily_run_boundary.py`'s established pattern."""
    recorded: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs: Any) -> MagicMock:
        recorded.append(cmd)
        result = MagicMock()
        result.returncode = 0
        return result

    monkeypatch.setattr(wrapper.subprocess, "run", _fake_run)

    now_et = datetime(2030, 8, 10, 22, 0, 0, tzinfo=wrapper.EASTERN)
    exit_code = wrapper.main(now_et=now_et)

    assert exit_code == 0
    assert len(recorded) == 1
    cmd = recorded[0]
    assert "run_market_discovery" in cmd[2]
    assert "--mode" in cmd
    assert cmd[cmd.index("--mode") + 1] == "delta"


def test_already_completed_research_day_does_not_launch_subprocess(
    _no_close_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    today = date(2026, 8, 10)
    _complete_delta_run(_no_close_session, window_start=today)

    recorded: list[list[str]] = []
    monkeypatch.setattr(
        wrapper.subprocess, "run", lambda cmd, **kw: recorded.append(cmd) or MagicMock(returncode=0)
    )

    now_et = datetime(2026, 8, 10, 22, 0, 0, tzinfo=wrapper.EASTERN)
    exit_code = wrapper.main(now_et=now_et)

    assert exit_code == 0
    assert recorded == []


def test_wrong_hour_does_not_launch_subprocess(
    _no_close_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: list[list[str]] = []
    monkeypatch.setattr(
        wrapper.subprocess, "run", lambda cmd, **kw: recorded.append(cmd) or MagicMock(returncode=0)
    )

    now_et = datetime(2026, 8, 10, 21, 0, 0, tzinfo=wrapper.EASTERN)
    exit_code = wrapper.main(now_et=now_et)

    assert exit_code == 0
    assert recorded == []


def test_correct_hour_trigger_refreshes_market_context(
    _no_close_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2026-08-11 finding: FRED's SOFR/HY OAS series had never been
    refreshed since their one-time Milestone 5 seed — nothing called
    `sync_series` on any recurring basis. The nightly wrapper must now
    call it on every correct-hour trigger, independent of whether a
    market-discovery research day already completed."""
    calls: list[str] = []
    monkeypatch.setattr(
        wrapper,
        "_refresh_market_context",
        lambda db, **kw: calls.append("refreshed"),
    )
    # A market-discovery cycle already completed for today — the delta
    # subprocess must NOT launch, but the FRED refresh must still happen,
    # proving the two are genuinely independent.
    today = date(2026, 8, 10)
    _complete_delta_run(_no_close_session, window_start=today)
    monkeypatch.setattr(wrapper.subprocess, "run", lambda cmd, **kw: MagicMock(returncode=0))

    now_et = datetime(2026, 8, 10, 22, 0, 0, tzinfo=wrapper.EASTERN)
    exit_code = wrapper.main(now_et=now_et)

    assert exit_code == 0
    assert calls == ["refreshed"]


def test_wrong_hour_trigger_does_not_refresh_market_context(
    _no_close_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other Railway trigger (wrong DST regime) must not refresh FRED
    either — only one trigger per night should ever touch it, matching
    the research-cycle no-op."""
    calls: list[str] = []
    monkeypatch.setattr(
        wrapper,
        "_refresh_market_context",
        lambda db, **kw: calls.append("refreshed"),
    )

    now_et = datetime(2026, 8, 10, 21, 0, 0, tzinfo=wrapper.EASTERN)
    exit_code = wrapper.main(now_et=now_et)

    assert exit_code == 0
    assert calls == []


def _fake_observation(series_id: str, obs_date: date) -> ObservationSyncResult:
    return ObservationSyncResult(
        observation=FredObservation(
            id=uuid4(),
            series_id=series_id,
            obs_date=obs_date,
            value=Decimal("1.23"),
            provenance_id=uuid4(),
        ),
        observation_created=True,
    )


def test_refresh_market_context_skips_gracefully_without_api_key(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        wrapper.fred_provider, "sync_series", lambda *a, **kw: calls.append("called")
    )

    wrapper._refresh_market_context(db_session, fred_api_key=None, user_agent="test-agent")

    assert calls == []  # never attempted a call with no key configured


def test_refresh_market_context_isolates_per_series_failure(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One series (e.g. a transient FRED HTTP error) failing must not
    prevent the other from being refreshed — per-provider isolation,
    same convention as the rest of this codebase."""
    attempted: list[str] = []

    def _fake_sync(
        db: Session, http_client: object, *, api_key: str, series_id: str, category: str
    ) -> FredSyncResult:
        attempted.append(series_id)
        if series_id == "SOFR":
            raise RuntimeError("simulated transient FRED HTTP error")
        return FredSyncResult(
            series=FredSeriesRegistry(
                series_id=series_id,
                title="Test series",
                units="Percent",
                frequency="Daily",
                category=category,
                last_synced_at=datetime.now(tz=UTC),
            ),
            observations=[_fake_observation(series_id, date(2026, 8, 10))],
        )

    monkeypatch.setattr(wrapper.fred_provider, "sync_series", _fake_sync)

    # Must not raise despite SOFR failing.
    wrapper._refresh_market_context(db_session, fred_api_key="test-key", user_agent="test-agent")

    assert attempted == ["SOFR", "BAMLH0A0HYM2"]
