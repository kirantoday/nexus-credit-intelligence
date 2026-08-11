"""Nightly scheduled entry point for the normal daily/delta research cycle
(PLAN.md 24.6) — the thin wrapper a Railway Cron trigger invokes, never the
production pipeline itself.

Why this exists: Railway Cron Jobs evaluate schedules in UTC only (no
timezone parameter — verified against Railway's own docs, not guessed), so
a single static UTC cron expression cannot correctly represent "10:00 PM
America/New_York" across a DST transition. The safe pattern used here needs
no third-party scheduler and stays on Railway's native cron: TWO Railway
cron triggers are configured (one at the UTC instant that is currently
10:00 PM Eastern Daylight Time, one at the UTC instant that is currently
10:00 PM Eastern Standard Time), both invoking this exact script every
night. This script uses `zoneinfo.ZoneInfo("America/New_York")` — the real
IANA timezone database, which already encodes the correct US DST
transition dates without this codebase hardcoding any of them — to
determine which of the two triggers is the "real" 10 PM ET one on any
given night; the other exits immediately as a no-op. `TZ=America/New_York`
should also be set on the Railway cron service's own environment (belt and
suspenders): the underlying `run_market_discovery.py --mode delta` call
computes its window via naive `date.today()`, which is UTC on an
unconfigured container — setting `TZ` makes that resolve to the correct
Eastern business date too, not just this wrapper's own hour check.

Duplicate-run protection is layered, not reinvented: Railway itself skips
an overlapping trigger if the previous invocation is still running (its own
platform-level protection); this script additionally checks
`market_discovery_repository.get_latest_successful_daily_run` (the same
function the Morning Brief itself uses to determine "today's research day")
before doing any work, so even a manual re-trigger or a missed Railway skip
can never launch a second real daily cycle for a research day already
completed. No new scheduling-state table or mechanism is introduced —
this reuses the existing `market_discovery_run` daily-run-boundary concept
end to end.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.db.session import SessionLocal
from app.repositories import market_discovery_repository

EASTERN = ZoneInfo("America/New_York")

# The target wall-clock hour in America/New_York. Both Railway triggers fire
# once daily; only the one landing in this hour actually runs the pipeline.
TARGET_HOUR_ET = 22

# Recurring nightly budget defaults — configurable via Railway env vars so a
# future change doesn't require a code deploy. These defaults match the
# limits explicitly authorized for the 2026-08-10 run; they are a
# placeholder standing policy, not re-derived here, and should be revisited
# by explicit decision if real nightly volume differs materially.
_DEFAULT_MAX_AI_COST_USD = "2.00"
_DEFAULT_MAX_AI_CALLS = "300"
_DEFAULT_MAX_SONNET_CALLS = "75"


def should_run(now_et: datetime, latest_daily_run_window_start: date | None) -> tuple[bool, str]:
    """Pure decision logic, deliberately separated from any I/O so it can be
    unit-tested against synthetic timestamps without a database or
    subprocess. Returns `(should_run, reason)` — `reason` is always
    populated, matching this codebase's "never silently drop a decision"
    convention (e.g. `market_discovery_candidate.resolution_reason`).
    """
    if now_et.hour != TARGET_HOUR_ET:
        return False, (
            f"wrong trigger for this DST regime: current America/New_York hour is "
            f"{now_et.hour:02d}, target is {TARGET_HOUR_ET:02d} — no-op, the other "
            "Railway trigger is the active one tonight"
        )
    if latest_daily_run_window_start == now_et.date():
        return False, (
            f"a daily research cycle already completed for {now_et.date().isoformat()} "
            "(market_discovery_run.window_start_date match) — no-op, not launching a "
            "duplicate run"
        )
    return True, (
        f"America/New_York hour matches target ({TARGET_HOUR_ET:02d}:00) and no daily "
        f"research cycle has completed yet for {now_et.date().isoformat()} — launching "
        "the normal delta run"
    )


def main(argv: list[str] | None = None, *, now_et: datetime | None = None) -> int:
    """`now_et` is exposed as an injectable parameter purely for deterministic
    testing (see `tests/unit/test_run_nightly_scheduled_discovery.py`) —
    every real invocation (including both Railway cron triggers) leaves it
    unset and gets the actual current time."""
    del argv  # no CLI arguments — this is a scheduler entry point, not an operator tool
    settings = get_settings()
    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    now_et = now_et if now_et is not None else datetime.now(EASTERN)
    db = SessionLocal()
    try:
        latest_daily = market_discovery_repository.get_latest_successful_daily_run(db)
        latest_window_start = latest_daily.window_start_date if latest_daily else None
    finally:
        db.close()

    run_now, reason = should_run(now_et, latest_window_start)
    print(f"[{now_et.isoformat()}] {reason}")
    if not run_now:
        return 0

    import os

    max_cost = os.environ.get("NIGHTLY_MAX_AI_COST_USD", _DEFAULT_MAX_AI_COST_USD)
    max_calls = os.environ.get("NIGHTLY_MAX_AI_CALLS", _DEFAULT_MAX_AI_CALLS)
    max_sonnet = os.environ.get("NIGHTLY_MAX_SONNET_CALLS", _DEFAULT_MAX_SONNET_CALLS)
    print(
        f"Launching: python -m app.scripts.run_market_discovery --mode delta "
        f"--max-ai-cost-usd {max_cost} --max-ai-calls {max_calls} "
        f"--max-sonnet-calls {max_sonnet} (environment={settings.environment})"
    )

    child_env = {**os.environ, "TZ": "America/New_York"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.scripts.run_market_discovery",
            "--mode",
            "delta",
            "--max-ai-cost-usd",
            max_cost,
            "--max-ai-calls",
            max_calls,
            "--max-sonnet-calls",
            max_sonnet,
        ],
        env=child_env,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
