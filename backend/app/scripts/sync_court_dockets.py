"""Sync entries for every already-linked CourtListener docket (PLAN.md
sections 4.5, 15, Milestone 7).

    python -m app.scripts.sync_court_dockets [--backfill]

Writes through the same Provider DTO -> Normalizer -> Canonical Domain
Object -> Repository -> Evidence Evaluation -> Alert Synthesis pipeline as
every interactive request (PLAN.md section 3), applied to court dockets
instead of SEC filings. Opens its own session directly via
`app.db.session.SessionLocal` (not the FastAPI `get_db` dependency), since
`court_docket_service` — like `filing_monitor_service` — manages its own
per-docket commit/rollback boundaries so one docket's failure never loses
another's already-committed work in the same run.

`--backfill` labels any resulting alerts `is_backfill=True` — appropriate
for a docket's *first* sync (which necessarily ingests its entire historical
entry list at once, not real overnight monitoring) and for the controlled
historical demo this milestone's live verification uses. There is no
watermark/delta concept for dockets the way `filing_monitor_run` has for SEC
filings (PLAN.md section 4.5 defines no `docket_monitor_run` table) —
idempotency is per-entry via `courtlistener_entry_id`, so re-running is
always safe and only ever processes genuinely new entries regardless of this
flag.

**Target production schedule (documented, not activated)**: Railway Cron,
alongside `run_overnight_filing_monitor.py` (PLAN.md 24.6) — not wired into
`railway.toml` or deployed this milestone.
"""

from __future__ import annotations

import argparse
import sys

from app.ai.factory import LLMConfigurationError, get_llm_provider
from app.config import get_settings
from app.db.session import SessionLocal
from app.providers.courtlistener.client import build_http_client
from app.repositories import court_docket_repository
from app.services import court_docket_service


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync every linked court docket's entries.")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Label resulting alerts as Historical (a docket's first sync).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1
    if not settings.courtlistener_api_token:
        print("ERROR: COURTLISTENER_API_TOKEN is not configured.", file=sys.stderr)
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

    http_client = build_http_client(
        user_agent="nexus-credit-intelligence-research (sync_court_dockets)",
        api_token=settings.courtlistener_api_token,
    )
    db = SessionLocal()

    dockets_synced = 0
    entries_discovered = 0
    alerts_created = 0
    errors: list[str] = []
    try:
        dockets = court_docket_repository.list_dockets_linked_to_issuers(db)
        print(f"Syncing {len(dockets)} linked docket(s)...")
        for docket in dockets:
            try:
                result = court_docket_service.sync_one_docket(
                    db,
                    http_client,
                    llm,
                    docket=docket,
                    environment=settings.environment,
                    is_backfill=args.backfill,
                )
                db.commit()
                dockets_synced += 1
                entries_discovered += result.entries_discovered
                alerts_created += result.alerts_created
                print(
                    f"  {docket.case_name} ({docket.docket_number}): "
                    f"entries_discovered={result.entries_discovered} "
                    f"alerts_created={result.alerts_created}"
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - per-docket isolation, mirrors filing_monitor_service
                db.rollback()
                errors.append(f"docket {docket.id} ({docket.case_name}): {exc}")
                print(f"  ERROR syncing {docket.case_name}: {exc}", file=sys.stderr)
    finally:
        db.close()
        http_client.close()

    print("\n=== Summary ===")
    print(f"Dockets synced:      {dockets_synced}")
    print(f"Entries discovered:  {entries_discovered}")
    print(f"Alerts created:      {alerts_created}")
    print(f"Errors:              {len(errors)}")
    if errors:
        for error in errors:
            print(f"  - {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
