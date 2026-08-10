"""Overnight Distress Filing Monitor — standalone entry point (PLAN.md 24.6).

    python -m app.scripts.run_overnight_filing_monitor \
        --mode {baseline|delta|backfill} [--backfill-days N]

Writes through the same Provider DTO -> Normalizer -> Canonical Domain Object
-> Repository -> Evidence Evaluation -> Alert Synthesis pipeline as every
interactive request (PLAN.md section 3, section 23.5) — this script is an
alternate trigger for the existing pipeline, never a separate write path. It
opens its own database session directly via `app.db.session.SessionLocal`
(not the FastAPI `get_db` dependency, since `filing_monitor_service` manages
its own per-issuer commit/rollback boundaries — see that module's docstring).

**Target production schedule (documented, not activated — PLAN.md 24.6)**:
Railway Cron, `0 9 * * *` (09:00 UTC, approximately 5:00 AM Eastern),
command `python -m app.scripts.run_overnight_filing_monitor --mode delta`.
Not wired into `railway.toml` or deployed this milestone — no production
Railway environment is configured yet (Milestone 15 territory).
"""

from __future__ import annotations

import argparse
import sys

from app.ai.factory import LLMConfigurationError, build_model_router
from app.config import get_settings
from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.db.session import SessionLocal
from app.providers.base.http_client import ThrottledHttpClient
from app.services import filing_monitor_service


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Overnight Distress Filing Monitor.")
    parser.add_argument(
        "--mode",
        choices=["baseline", "delta", "backfill"],
        required=True,
        help="baseline: establish a watermark, ingest nothing. delta: process filings since "
        "the last successful run. backfill: process a fixed lookback window, labeled by real "
        "event dates as Historical, never presented as newly filed overnight.",
    )
    parser.add_argument(
        "--backfill-days",
        type=int,
        default=None,
        help="Required with --mode backfill; the lookback window in days.",
    )
    args = parser.parse_args(argv)
    if args.mode == "backfill" and not args.backfill_days:
        parser.error("--backfill-days is required when --mode backfill")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1
    if not settings.sec_user_agent:
        print("ERROR: SEC_USER_AGENT is not configured.", file=sys.stderr)
        return 1

    try:
        router = build_model_router(settings)
        print(f"AI evidence review: enabled (LLM_PROVIDER={settings.llm_provider}).")
    except LLMConfigurationError as exc:
        router = None
        print(
            f"AI evidence review: disabled ({exc}). Running deterministic-only — this is a "
            "supported, fully operational mode, not a degraded one."
        )

    http_client = ThrottledHttpClient(user_agent=settings.sec_user_agent)
    db = SessionLocal()
    try:
        run = filing_monitor_service.run_monitor(
            db,
            http_client,
            router,
            mode=FilingMonitorRunMode(args.mode),
            backfill_days=args.backfill_days,
            environment=settings.environment,
        )
    finally:
        db.close()
        http_client.close()

    print(f"Run {run.id} — status={run.status.value} mode={run.mode.value}")
    print(f"  issuers_checked:     {run.issuers_checked}")
    print(f"  filings_discovered:  {run.filings_discovered}")
    print(f"  filings_processed:   {run.filings_processed}")
    print(f"  alerts_created:      {run.alerts_created}")
    print(f"  errors_count:        {run.errors_count}")
    if run.error_summary:
        print(f"  error_summary:       {run.error_summary}")
    print(f"  previous_watermark:  {run.previous_watermark}")
    print(f"  resulting_watermark: {run.resulting_watermark}")

    success_statuses = (FilingMonitorRunStatus.SUCCESS, FilingMonitorRunStatus.BASELINE_ESTABLISHED)
    return 0 if run.status in success_statuses else 1


if __name__ == "__main__":
    sys.exit(main())
