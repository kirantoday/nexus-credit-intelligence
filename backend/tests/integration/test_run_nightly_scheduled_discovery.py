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
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.domain.market_discovery import MarketDiscoveryRunCreate
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
    """
    monkeypatch.setattr(wrapper, "SessionLocal", lambda: db_session)
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
