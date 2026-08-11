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

Also refreshes the two FRED market-context series (SOFR, HY OAS) on every
real (non-no-op) trigger — found 2026-08-11 to have never been refreshed
since their one-time Milestone 5 seed (`app.providers.fred.provider.
sync_series` was never wired into any recurring job). This refresh is
deliberately independent of the market-discovery duplicate-run check
above (a different data source, a different cadence — FRED publishing
its own observations is not "a research day"), and a FRED-side failure
never blocks or is blocked by the research cycle launch below (the same
per-provider isolation this codebase already uses everywhere else).
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.fred import provider as fred_provider
from app.repositories import market_discovery_repository

# The only two FRED series Market Context displays (PLAN.md section 18
# step 5) — (series_id, category), matching `market_context_service.py`'s
# own `_SOFR_SERIES_ID`/`_HY_OAS_SERIES_ID` and the categories used at
# their original Milestone 5 seed.
_MARKET_CONTEXT_SERIES: tuple[tuple[str, str], ...] = (
    ("SOFR", "rate"),
    ("BAMLH0A0HYM2", "spread"),
)

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


def _refresh_market_context(
    db: Session, *, fred_api_key: str | None, user_agent: str | None
) -> None:
    """Refreshes only `SOFR`/`BAMLH0A0HYM2` via the existing, unmodified
    `fred_provider.sync_series` (idempotent per `(series_id, obs_date)` —
    safe to call every night regardless of what's already stored). Never
    raises: a FRED-side failure (missing key, transient HTTP error) is
    logged and swallowed, matching this codebase's per-provider isolation
    convention — the research cycle below must never be blocked by this.
    """
    if not fred_api_key:
        print("Market Context refresh: skipped (FRED_API_KEY not configured).")
        return
    http_client = ThrottledHttpClient(user_agent=user_agent or "nexus-credit-intelligence/1.0")
    try:
        for series_id, category in _MARKET_CONTEXT_SERIES:
            try:
                result = fred_provider.sync_series(
                    db, http_client, api_key=fred_api_key, series_id=series_id, category=category
                )
                db.commit()
                new_count = sum(1 for o in result.observations if o.observation_created)
                latest = max(result.observations, key=lambda o: o.observation.obs_date)
                print(
                    f"Market Context refresh: {series_id} — {new_count} new observation(s), "
                    f"latest={latest.observation.obs_date} value={latest.observation.value}"
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - per-series isolation, never blocks the research cycle
                db.rollback()
                print(f"Market Context refresh: {series_id} FAILED ({exc}) — continuing.")
    finally:
        http_client.close()


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
    is_correct_trigger = now_et.hour == TARGET_HOUR_ET
    db = SessionLocal()
    try:
        latest_daily = market_discovery_repository.get_latest_successful_daily_run(db)
        latest_window_start = latest_daily.window_start_date if latest_daily else None
        # Independent of the research-cycle duplicate check below: FRED
        # publishes on its own cadence, not "a research day," and refreshing
        # it is fully idempotent, so it runs on every real (correct-hour)
        # trigger regardless of whether a market-discovery cycle already
        # completed for today.
        if is_correct_trigger:
            _refresh_market_context(
                db, fred_api_key=settings.fred_api_key, user_agent=settings.sec_user_agent
            )
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
