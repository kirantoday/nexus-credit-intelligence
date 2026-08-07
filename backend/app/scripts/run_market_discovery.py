"""SEC Market Discovery — standalone entry point (PLAN.md Milestone 7.5).

    python -m app.scripts.run_market_discovery \\
        --mode {baseline|delta|backfill} [--start YYYY-MM-DD --end YYYY-MM-DD] \\
        [--force-reprocess]

Writes through the same pipeline as every other trigger of this codebase's
evidence/alert chain (`app.services.market_discovery_service`, which itself
hands off to `app.services.filing_monitor_service.process_issuer_filings`
for any resolved issuer) — this script is an alternate entry point, never a
separate write path. Opens its own database session directly via
`app.db.session.SessionLocal`, matching `run_overnight_filing_monitor.py`'s
established pattern (`market_discovery_service` manages its own per-
candidate/per-issuer commit/rollback boundaries).

**Milestone 7.5's explicit hard approval gate**: this script's `backfill`
mode does not itself limit the requested window — the caller decides the
window. The 2026-01-01..2026-08-06 historical backfill must not be run
until the 2026-07-01..2026-08-06 pilot has been run, manually reviewed, and
explicitly approved by the user. This script does not enforce that
politically — it enforces it by only ever being invoked for the approved
window, one run at a time, by whoever is operating it.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.factory import LLMConfigurationError, get_llm_provider
from app.ai.providers.base import LLMProvider
from app.config import Settings, get_settings
from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.db.session import SessionLocal
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.courtlistener.client import build_http_client as build_courtlistener_http_client
from app.services import market_discovery_service
from app.services.enrichment_orchestrator import EnrichmentClients
from app.services.enrichment_orchestrator import enrich_issuer as default_enrich_issuer

# SEC's own fair-access ceiling is ~10 req/sec; a market-wide discovery
# scan issues many more requests than a known-issuer refresh (one search
# call per query per page, plus a full submissions+filing-document fetch
# per newly-resolved issuer) — a more conservative interval than the
# default 0.15s keeps this comfortably inside fair-access even under
# back-to-back pagination.
_DISCOVERY_MIN_INTERVAL_SECONDS = 0.5


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SEC Market Discovery.")
    parser.add_argument(
        "--mode",
        choices=["baseline", "delta", "backfill"],
        required=True,
        help="baseline: establish a watermark, discover nothing. delta: discover since the "
        "last successful run's watermark. backfill: discover within an explicit --start/--end "
        "window, labeled by real event dates, never presented as newly filed overnight.",
    )
    parser.add_argument("--start", type=str, default=None, help="Required with --mode backfill.")
    parser.add_argument("--end", type=str, default=None, help="Required with --mode backfill.")
    parser.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Reprocess (cik, accession_no) pairs already examined by an earlier run, even if "
        "the active rule version hasn't changed since. See market_discovery_candidate's "
        "docstring: source identity and processing state are deliberately kept separate so "
        "deliberate reprocessing is always possible, never architecturally foreclosed.",
    )
    args = parser.parse_args(argv)
    if args.mode == "backfill" and (not args.start or not args.end):
        parser.error("--start and --end are required when --mode backfill")
    return args


def _build_enrichment_clients(
    settings: Settings, sec_http_client: ThrottledHttpClient
) -> EnrichmentClients:
    """Assembles the per-provider clients the enrichment orchestrator needs.
    SEC reuses the discovery run's own client (same fair-access budget);
    CourtListener/OpenFIGI stay `None` — and the orchestrator marks them
    `unavailable` per-issuer, never crashing the run — when their optional
    credentials aren't configured, matching this project's established
    "stays operational without an optional credential" pattern.
    """
    assert settings.sec_user_agent is not None
    user_agent = settings.sec_user_agent
    courtlistener_client = (
        build_courtlistener_http_client(
            user_agent=user_agent, api_token=settings.courtlistener_api_token
        )
        if settings.courtlistener_api_token
        else None
    )
    openfigi_client = ThrottledHttpClient(
        user_agent=user_agent,
        min_interval_seconds=6.0,
        extra_headers=(
            {"X-OPENFIGI-APIKEY": settings.openfigi_api_key} if settings.openfigi_api_key else None
        ),
    )
    return EnrichmentClients(
        sec=sec_http_client, courtlistener=courtlistener_client, openfigi=openfigi_client
    )


def _counting_enrich_issuer(
    counts: Counter[tuple[str, str]],
) -> market_discovery_service.EnrichIssuerFn:
    def _fn(
        db: Session,
        issuer_id: UUID,
        clients: EnrichmentClients,
        llm: LLMProvider | None,
        *,
        environment: str,
        force: bool,
    ) -> object:
        results = default_enrich_issuer(
            db, issuer_id, clients, llm, environment=environment, force=force
        )
        for provider, status in results.items():
            counts[(provider.value, status.status.value)] += 1
        return results

    return _fn


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
        llm = get_llm_provider(settings)
        print(f"AI evidence review: enabled (LLM_PROVIDER={settings.llm_provider}).")
    except LLMConfigurationError as exc:
        llm = None
        print(
            f"AI evidence review: disabled ({exc}). Running deterministic-only — this is a "
            "supported, fully operational mode, not a degraded one."
        )

    http_client = ThrottledHttpClient(
        user_agent=settings.sec_user_agent, min_interval_seconds=_DISCOVERY_MIN_INTERVAL_SECONDS
    )
    enrichment_clients = _build_enrichment_clients(settings, http_client)
    courtlistener_configured = "yes" if enrichment_clients.courtlistener else "no (unavailable)"
    print(
        "Enrichment providers configured: "
        f"sec=yes, courtlistener={courtlistener_configured}, openfigi=yes"
    )
    enrichment_counts: Counter[tuple[str, str]] = Counter()

    db = SessionLocal()
    started_at = time.monotonic()
    try:
        run = market_discovery_service.run_discovery(
            db,
            http_client,
            llm,
            mode=FilingMonitorRunMode(args.mode),
            window_start=date.fromisoformat(args.start) if args.start else None,
            window_end=date.fromisoformat(args.end) if args.end else None,
            environment=settings.environment,
            force_reprocess=args.force_reprocess,
            enrichment_clients=enrichment_clients,
            enrich_issuer_fn=_counting_enrich_issuer(enrichment_counts),
        )
    finally:
        db.close()
        http_client.close()
        if enrichment_clients.courtlistener is not None:
            enrichment_clients.courtlistener.close()
        if enrichment_clients.openfigi is not None:
            enrichment_clients.openfigi.close()
    elapsed_seconds = time.monotonic() - started_at

    print(f"Run {run.id} — status={run.status.value} mode={run.mode.value}")
    print(f"  window:                  {run.window_start_date} .. {run.window_end_date}")
    print(f"  queries_executed:        {run.queries_executed}")
    print(f"  filings_examined:        {run.filings_examined}")
    print(f"  candidate_filings:       {run.candidate_filings}")
    print(f"  issuers_resolved_existing: {run.issuers_resolved_existing}")
    print(f"  issuers_resolved_new:      {run.issuers_resolved_new}")
    print(f"  issuers_ambiguous:         {run.issuers_ambiguous}")
    print(f"  issuers_rejected:          {run.issuers_rejected}")
    print(f"  evidence_created:        {run.evidence_created}")
    print(f"  alerts_created:          {run.alerts_created}")
    print(f"  errors_count:            {run.errors_count}")
    if run.error_summary:
        print(f"  error_summary:           {run.error_summary}")
    print(f"  previous_watermark:      {run.previous_watermark}")
    print(f"  resulting_watermark:     {run.resulting_watermark}")
    print(f"  elapsed_seconds:         {elapsed_seconds:.1f}")
    print("  enrichment_results (provider, status -> count):")
    for (provider, status), count in sorted(enrichment_counts.items()):
        print(f"    {provider:14s} {status:24s} {count}")

    success_statuses = (FilingMonitorRunStatus.SUCCESS, FilingMonitorRunStatus.BASELINE_ESTABLISHED)
    return 0 if run.status in success_statuses else 1


if __name__ == "__main__":
    sys.exit(main())
