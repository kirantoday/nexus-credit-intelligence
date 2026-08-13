"""SEC Market Discovery — standalone entry point (PLAN.md Milestone 7.5,
AI cost-control correction in Milestone 7.5.3).

    python -m app.scripts.run_market_discovery \\
        --mode {baseline|delta|backfill} [--start YYYY-MM-DD --end YYYY-MM-DD] \\
        [--force-reprocess] \\
        [--ai-mode {full|zero}] \\
        [--max-ai-calls N] [--max-ai-cost-usd X] [--max-sonnet-calls N]

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

**Milestone 7.5.3's AI cost-control correction**: `--ai-mode zero` runs the
full deterministic pipeline (SEC discovery, issuer resolution, filing
ingestion, Layer-1 evidence extraction) with zero Anthropic calls — every
bundle that would have needed AI is left `deferred` (no alert created,
still reachable by a later AI-enabled run via the same `bundle_key`
idempotency check) rather than downgraded to a permanent deterministic
alert. This is the "measure new material before approving paid AI
processing" mode PLAN.md Milestone 7.5.3 requires. `--ai-mode full`
(default) routes through `app.ai.model_router.ModelRouter`
(deterministic -> Haiku -> Sonnet escalation) with a hard, centrally
enforced budget — once any configured `--max-ai-*` limit is reached, zero
further paid AI calls are made for the rest of the run; already-completed
deterministic work is never rolled back.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.factory import LLMConfigurationError, build_model_router
from app.ai.model_router import AiCallBudget, ModelRouter, default_routing_config
from app.config import Settings, get_settings
from app.core.types import FilingMonitorRunMode, FilingMonitorRunStatus
from app.db.session import SessionLocal
from app.providers.base.http_client import ThrottledHttpClient
from app.providers.courtlistener.client import build_http_client as build_courtlistener_http_client
from app.repositories import ai_call_log_repository, research_evidence_repository
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
    parser.add_argument(
        "--ai-mode",
        choices=["full", "zero"],
        default="full",
        help="full (default): route evidence review through Haiku/Sonnet per policy, subject "
        "to any --max-ai-* budget. zero: deterministic pipeline only, zero Anthropic calls — "
        "bundles that would need AI are deferred (no alert created), not downgraded, so a "
        "later --ai-mode full run over the same window can still review them. Use this to "
        "measure the volume of new material before approving paid AI processing.",
    )
    parser.add_argument(
        "--max-ai-calls",
        type=int,
        default=None,
        help="Hard ceiling on total Anthropic calls (Haiku + Sonnet) this run will ever make. "
        "Unset = unlimited.",
    )
    parser.add_argument(
        "--max-ai-cost-usd",
        type=float,
        default=None,
        help="Hard ceiling on estimated AI spend (USD) this run will ever make. Unset = "
        "unlimited. Cost is estimated from app.ai.pricing, not billed truth.",
    )
    parser.add_argument(
        "--max-sonnet-calls",
        type=int,
        default=None,
        help="Hard ceiling on Sonnet escalation calls specifically (Haiku calls are not "
        "counted against this). Unset = unlimited.",
    )
    parser.add_argument(
        "--estimate-only",
        action="store_true",
        help="Print the pre-run cost-estimation report (candidate/bundle counts already on "
        "file, configured budgets) and exit without running discovery at all.",
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
            user_agent=user_agent,
            api_token=settings.courtlistener_api_token,
            max_retry_after_seconds=settings.courtlistener_retry_after_max_seconds,
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
        router: ModelRouter | None,
        *,
        environment: str,
        force: bool,
        discovery_run_id: UUID | None = None,
    ) -> object:
        results = default_enrich_issuer(
            db,
            issuer_id,
            clients,
            router,
            environment=environment,
            force=force,
            discovery_run_id=discovery_run_id,
        )
        for provider, status in results.items():
            counts[(provider.value, status.status.value)] += 1
        return results

    return _fn


def _print_pre_run_estimate(db: Session, settings: Settings, args: argparse.Namespace) -> None:
    """PLAN.md Milestone 7.5.3 section 12: report what's knowable *before*
    spending anything. `research_evidence.confidence` values already on
    file are the only honest sample this codebase has of "how strong is a
    typical evidence match" — a live SEC search for a *new* window can
    surface a materially different volume and mix, so this is explicitly
    labeled an estimate, never a forecast of this specific run's actual
    cost.
    """
    sample = research_evidence_repository.sample_confidence_values(db, limit=5000)
    floor = settings.ai_deterministic_confidence_floor
    haiku_threshold = settings.ai_haiku_confidence_threshold
    no_ai = sum(1 for c in sample if c < floor)
    would_need_ai = len(sample) - no_ai
    print("=== Pre-run AI cost estimate (based on prior evidence data on file) ===")
    print(f"  sample size (existing research_evidence.confidence values): {len(sample)}")
    print(f"  would need no AI at all (below confidence floor {floor}): {no_ai}")
    print(f"  would reach model review: {would_need_ai}")
    print(
        "  of those, share historically routable to Haiku vs. requiring Sonnet escalation is "
        "NOT reliably knowable ahead of a live model call (it depends on Haiku's own reported "
        f"confidence against threshold {haiku_threshold}, not on Layer-1 confidence alone) — "
        "not estimated here to avoid inventing a precise number PLAN.md explicitly warns "
        "against fabricating."
    )
    print(
        f"  configured budget: max_ai_calls={args.max_ai_calls or 'unlimited'} "
        f"max_ai_cost_usd={args.max_ai_cost_usd or 'unlimited'} "
        f"max_sonnet_calls={args.max_sonnet_calls or 'unlimited'}"
    )
    print(
        "  NOTE: this is a sample from data already on file, not a prediction of how many "
        "NEW candidates this specific run's live SEC search will surface."
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1
    if not settings.sec_user_agent:
        print("ERROR: SEC_USER_AGENT is not configured.", file=sys.stderr)
        return 1

    if args.estimate_only:
        db = SessionLocal()
        try:
            _print_pre_run_estimate(db, settings, args)
        finally:
            db.close()
        return 0

    budget = AiCallBudget(
        max_calls=args.max_ai_calls,
        max_cost_usd=args.max_ai_cost_usd,
        max_sonnet_calls=args.max_sonnet_calls,
    )

    router: ModelRouter | None
    if args.ai_mode == "zero":
        router = ModelRouter(
            haiku=None,
            sonnet=None,
            config=default_routing_config(settings),
            budget=budget,
        )
        print("AI evidence review: zero-AI mode — deterministic pipeline only, no Anthropic calls.")
    else:
        try:
            router = build_model_router(settings, budget=budget)
            print(
                f"AI evidence review: enabled, routed (Haiku={settings.ai_haiku_model_id}, "
                f"Sonnet={settings.ai_sonnet_model_id}, routing_enabled="
                f"{settings.ai_routing_enabled})."
            )
            print(
                f"AI budget: max_calls={args.max_ai_calls or 'unlimited'} "
                f"max_cost_usd={args.max_ai_cost_usd or 'unlimited'} "
                f"max_sonnet_calls={args.max_sonnet_calls or 'unlimited'}"
            )
        except LLMConfigurationError as exc:
            router = None
            print(
                f"AI evidence review: disabled ({exc}). Running deterministic-only — this is a "
                "supported, fully operational mode, not a degraded one."
            )

    http_client = ThrottledHttpClient(
        user_agent=settings.sec_user_agent,
        min_interval_seconds=_DISCOVERY_MIN_INTERVAL_SECONDS,
        # 2026-08-12/13 incident: SEC's full-text-search index
        # (efts.sec.gov) returned a bare, transient 500 on one query in
        # two consecutive production runs (different query each time) —
        # zero retries meant one flaky upstream response aborted an
        # otherwise-successful ~40-query run and stalled the daily-run
        # watermark. Reuses the same retry mechanism already proven for
        # CourtListener's 429s (`app.providers.courtlistener.client`),
        # just against SEC's transient-5xx set instead of a rate limit.
        retry_on_status=frozenset({500, 502, 503, 504}),
        max_retries=2,
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
            router,
            mode=FilingMonitorRunMode(args.mode),
            window_start=date.fromisoformat(args.start) if args.start else None,
            window_end=date.fromisoformat(args.end) if args.end else None,
            environment=settings.environment,
            force_reprocess=args.force_reprocess,
            enrichment_clients=enrichment_clients,
            enrich_issuer_fn=_counting_enrich_issuer(enrichment_counts),
        )
        ai_usage = ai_call_log_repository.aggregate_for_discovery_run(db, run.id)
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

    print("=== AI usage (this run, from ai_call_log) ===")
    print(f"  total_calls:          {ai_usage.total_calls}")
    print(f"  haiku_calls:          {ai_usage.haiku_calls}")
    print(f"  sonnet_calls:         {ai_usage.sonnet_calls}")
    print(f"  failed_calls:         {ai_usage.failed_calls}")
    print(f"  total_retries:        {ai_usage.total_retries}")
    print(f"  total_input_tokens:   {ai_usage.total_input_tokens}")
    print(f"  total_output_tokens:  {ai_usage.total_output_tokens}")
    print(f"  total_estimated_cost_usd: {ai_usage.total_estimated_cost_usd:.4f}")
    print(f"  cost_by_model:        {ai_usage.cost_by_model}")
    print(f"  cost_by_operation:    {ai_usage.cost_by_operation}")
    if router is not None:
        print(
            "  budget: deterministic_skips="
            f"{router.budget.deterministic_skips} deferred_no_budget="
            f"{router.budget.deferred_count} calls_blocked_by_budget="
            f"{router.budget.calls_blocked}"
        )
        if router.budget.deferred_count > 0:
            print(
                f"  NOTE: {router.budget.deferred_count} bundle(s) needed AI review but got "
                "none this run (zero-AI mode, or budget exhausted before any attempt) — no "
                "alert was created for them; a future AI-enabled run with budget available "
                "will still pick them up via the same bundle_key idempotency check."
            )

    success_statuses = (FilingMonitorRunStatus.SUCCESS, FilingMonitorRunStatus.BASELINE_ESTABLISHED)
    return 0 if run.status in success_statuses else 1


if __name__ == "__main__":
    sys.exit(main())
