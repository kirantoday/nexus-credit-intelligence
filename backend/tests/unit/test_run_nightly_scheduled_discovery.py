"""Unit tests for the DST-safe nightly scheduler wrapper's decision logic
(`app.scripts.run_nightly_scheduled_discovery.should_run`) — pure, no DB or
subprocess involved, exercising exactly the scenarios PLAN.md's nightly-
scheduling requirement calls out: EDT, EST, the wrong-trigger no-op in each
direction, a real DST-transition proof via `zoneinfo` (not hardcoded
transition dates), and the duplicate/already-completed no-op.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.scripts.run_nightly_scheduled_discovery import EASTERN, TARGET_HOUR_ET, should_run


def test_10pm_during_edt_runs() -> None:
    # 2026-07-15 is deep in Eastern Daylight Time (UTC-4).
    now_et = datetime(2026, 7, 15, 22, 0, 0, tzinfo=EASTERN)
    assert now_et.utcoffset() is not None
    assert now_et.utcoffset().total_seconds() == -4 * 3600
    run_now, reason = should_run(now_et, latest_daily_run_window_start=None)
    assert run_now is True
    assert "launching" in reason.lower()


def test_10pm_during_est_runs() -> None:
    # 2026-01-15 is deep in Eastern Standard Time (UTC-5).
    now_et = datetime(2026, 1, 15, 22, 0, 0, tzinfo=EASTERN)
    assert now_et.utcoffset().total_seconds() == -5 * 3600
    run_now, reason = should_run(now_et, latest_daily_run_window_start=None)
    assert run_now is True
    assert "launching" in reason.lower()


def test_wrong_trigger_noops_during_edt() -> None:
    # During EDT, the EST-timed trigger lands at 21:00 ET, not 22:00 — must no-op.
    now_et = datetime(2026, 7, 15, 21, 0, 0, tzinfo=EASTERN)
    run_now, reason = should_run(now_et, latest_daily_run_window_start=None)
    assert run_now is False
    assert "wrong trigger" in reason.lower()


def test_wrong_trigger_noops_during_est() -> None:
    # During EST, the EDT-timed trigger lands at 23:00 ET, not 22:00 — must no-op.
    now_et = datetime(2026, 1, 15, 23, 0, 0, tzinfo=EASTERN)
    run_now, reason = should_run(now_et, latest_daily_run_window_start=None)
    assert run_now is False
    assert "wrong trigger" in reason.lower()


def test_dst_transition_handled_by_zoneinfo_not_hardcoded_dates() -> None:
    """Construct the two Railway trigger instants (fixed UTC hours) on both
    sides of a real US DST transition and confirm zoneinfo alone — not any
    date table in this codebase — correctly flips which trigger lands on
    the target Eastern hour. 2026's US DST transitions: spring-forward
    2026-03-08 02:00 -> 03:00 (EST->EDT), fall-back 2026-11-01 02:00 -> 01:00
    (EDT->EST); IANA source of truth, not asserted here, only relied upon.

    Trigger A fires at 02:00 UTC daily; Trigger B fires at 03:00 UTC daily.
    """
    utc = ZoneInfo("UTC")

    # Before spring-forward (still EST, UTC-5): 02:00 UTC = 21:00 ET (Trigger
    # A, wrong), 03:00 UTC = 22:00 ET (Trigger B, correct).
    before_transition = date(2026, 3, 1)
    trigger_a_before = datetime(*before_transition.timetuple()[:3], 2, 0, tzinfo=utc).astimezone(
        EASTERN
    )
    trigger_b_before = datetime(*before_transition.timetuple()[:3], 3, 0, tzinfo=utc).astimezone(
        EASTERN
    )
    assert should_run(trigger_a_before, None)[0] is False
    assert should_run(trigger_b_before, None)[0] is True

    # After spring-forward (now EDT, UTC-4): 02:00 UTC = 22:00 ET (Trigger A,
    # now correct), 03:00 UTC = 23:00 ET (Trigger B, now wrong) — the flip
    # happens purely because zoneinfo knows the real transition date.
    after_transition = date(2026, 3, 15)
    trigger_a_after = datetime(*after_transition.timetuple()[:3], 2, 0, tzinfo=utc).astimezone(
        EASTERN
    )
    trigger_b_after = datetime(*after_transition.timetuple()[:3], 3, 0, tzinfo=utc).astimezone(
        EASTERN
    )
    assert should_run(trigger_a_after, None)[0] is True
    assert should_run(trigger_b_after, None)[0] is False


def test_duplicate_research_day_noops() -> None:
    now_et = datetime(2026, 8, 10, 22, 0, 0, tzinfo=EASTERN)
    run_now, reason = should_run(now_et, latest_daily_run_window_start=date(2026, 8, 10))
    assert run_now is False
    assert "already completed" in reason.lower()


def test_prior_days_completion_does_not_block_tonight() -> None:
    """A daily run that completed for a *different* research day (e.g.
    yesterday) must not block tonight's — only an exact match on today's
    date is a duplicate."""
    now_et = datetime(2026, 8, 10, 22, 0, 0, tzinfo=EASTERN)
    run_now, reason = should_run(now_et, latest_daily_run_window_start=date(2026, 8, 7))
    assert run_now is True
    assert "launching" in reason.lower()


def test_target_hour_constant_is_10pm() -> None:
    assert TARGET_HOUR_ET == 22
