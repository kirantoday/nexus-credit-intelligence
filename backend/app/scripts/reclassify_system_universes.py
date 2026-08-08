"""Reconciliation: recompute evidence-driven Research Universe memberships
from scratch, correcting anything the pre-Milestone-7.5.1 classification
bug already wrote (PLAN.md Milestone 7.5.1 section 9).

    python -m app.scripts.reclassify_system_universes [--dry-run]

Root cause (Milestone 7.5.1's audit): `universe_classification_service
.classify_issuer` used to gate automatic membership on `research_evidence`'s
raw Layer-1 deterministic severity, which has no concept of *whose* event a
matched phrase describes — live-verified in production: BlackSky
Technology's "chapter_11" evidence scored HIGH from a director's former
employer's bankruptcy, not BlackSky's own, and was auto-classified
`verified` anyway. The fix (this same milestone) makes `classify_issuer`
gate on the AI-reviewed alert's severity and a new `issuer_is_subject`
signal instead — but that live, incremental path is deliberately
upgrade-only (a membership already written `verified` is never
automatically downgraded), so the fix alone does not correct memberships
the bug already wrote before it existed. This script is the one-time,
explicit, auditable correction path Milestone 7.5.1 section 9 requires.

Two phases, run in order:

1. **Backfill** `alert_event.issuer_is_subject` for existing alerts that
   cover *definitive*-category evidence (Chapter 11 / bankruptcy-or-
   receivership / plan-confirmed) and currently have `issuer_is_subject
   IS NULL` (every alert created before this migration). Requires a fresh,
   targeted AI re-review per such alert — bounded to only this evidence
   category (a few hundred alerts, not all ~1,900), and the alert's
   already-correct `headline`/`explanation`/`severity` are left completely
   untouched; only the new structured field is added.
   Suggestive-category evidence needs no backfill: its existing
   `alert_event.severity` already reflects the AI's judgment correctly
   (live-verified repeatedly during the audit — MasterBrand, PagSeguro,
   Newmark Group, Commercial Metals, Ameresco, Skyworks, Whitestone REIT
   were all *already* correctly downgraded in their existing alerts; the
   bug was that classification never looked at that field at all).

2. **Recompute** every affected issuer's evidence-driven memberships from
   their *entire* evidence history using the corrected rules
   (`universe_classification_service.compute_expected_memberships`), then
   apply the result via `apply_correction` — which may upgrade, downgrade,
   add, or remove a membership, unlike the live path.

Only ever touches the 8 `system_seeded` evidence-driven collections
(`app.services.universe_classification_service._EVIDENCE_DRIVEN_UNIVERSES`)
— never a `manual_curated` universe, never an `issuer`/`sec_filing`/
`research_evidence`/`provenance` row, never deletes anything but a
membership row. Idempotent: re-running with no new evidence produces zero
changes.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.evidence_review import review_evidence_candidates
from app.ai.factory import LLMConfigurationError, get_llm_provider
from app.ai.llm_gate import check_send_to_llm
from app.ai.providers.base import LLMProvider
from app.config import get_settings
from app.core.types import DataClassification, VerificationStatus
from app.db.session import SessionLocal
from app.domain.evidence_bundle import group_evidence_into_bundles
from app.domain.research_evidence import ResearchEvidence
from app.repositories import (
    alert_repository,
    collection_repository,
    issuer_repository,
    research_evidence_repository,
)
from app.services import universe_classification_service
from app.services.alert_synthesis_service import evidence_to_candidate


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute evidence-driven Research Universe memberships from scratch."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing anything (backfill or memberships).",
    )
    return parser.parse_args(argv)


def _backfill_issuer_is_subject(
    db: Session, llm: LLMProvider | None, *, dry_run: bool
) -> Counter[str]:
    """Phase 1. Returns counts by outcome for reporting."""
    counts: Counter[str] = Counter()
    if llm is None:
        print(
            "  SKIPPED: no LLM provider configured — existing definitive-category alerts "
            "with issuer_is_subject=NULL are left as-is (classify_issuer falls back to "
            "Layer-1 severity for them, the pre-Milestone-7.5.1 behavior)."
        )
        return counts

    settings = get_settings()
    definitive_types = universe_classification_service.definitive_evidence_types()
    issuer_ids = research_evidence_repository.list_issuer_ids_with_evidence_types(
        db, definitive_types
    )
    print(f"  {len(issuer_ids)} issuer(s) with definitive-category evidence to check.", flush=True)

    for i, issuer_id in enumerate(issuer_ids, start=1):
        # The full per-issuer body — including the initial reads — is
        # inside this try block, not just the bundle loop: a transient
        # connection drop (live-observed, see TD-013 in PLAN.md) on *any*
        # query for this issuer must isolate to this issuer, exactly like
        # market_discovery_service's per-issuer boundary, not crash the
        # whole run and lose every issuer already processed before it.
        try:
            issuer = issuer_repository.get_issuer(db, issuer_id)
            if issuer is None:
                continue
            definitive_evidence = research_evidence_repository.list_evidence_by_issuer_and_types(
                db, issuer_id, definitive_types
            )
            # Only used to find *which bundles* contain definitive-category
            # evidence — the actual re-review candidates come from each
            # bundle's real alert.evidence_ids below, never from this
            # (necessarily incomplete, definitive-type-only) subset. Reviewing
            # just this subset in isolation would drop the rest of the
            # bundle's real context (e.g. a genuinely high-severity going-
            # concern item bundled alongside a boilerplate plan_confirmed
            # cover-page checkbox) that the original review actually saw.
            bundle_keys = {b.bundle_key for b in group_evidence_into_bundles(definitive_evidence)}
            print(
                f"  [{i}/{len(issuer_ids)}] {issuer.legal_name} "
                f"({len(bundle_keys)} bundle(s) to check)...",
                flush=True,
            )
            for bundle_key in bundle_keys:
                alert = alert_repository.get_alert_by_bundle_key(db, bundle_key)
                if alert is None or alert.issuer_is_subject is not None:
                    counts["already_known_or_no_alert"] += 1
                    continue

                gate = check_send_to_llm(
                    classification=DataClassification.PUBLIC,
                    entitlement=None,
                    environment=settings.environment,
                )
                if not gate.allowed:
                    counts["policy_blocked"] += 1
                    continue

                full_bundle_evidence = research_evidence_repository.list_evidence_by_ids(
                    db, alert.evidence_ids
                )
                candidates = [evidence_to_candidate(e) for e in full_bundle_evidence]
                result = review_evidence_candidates(
                    llm,
                    issuer_name=issuer.legal_name,
                    source_description=alert.primary_source_label,
                    candidates=candidates,
                )
                if result is None:
                    counts["ai_review_failed"] += 1
                    continue

                if not dry_run:
                    alert_repository.backfill_issuer_is_subject(
                        db, alert.id, issuer_is_subject=result.issuer_is_subject
                    )
                    db.commit()
                counts[f"backfilled_issuer_is_subject_{result.issuer_is_subject}"] += 1
        except Exception as exc:  # noqa: BLE001 - per-issuer isolation
            db.rollback()
            counts["errors"] += 1
            print(f"  ERROR backfilling issuer {issuer_id}: {exc}")

    return counts


def _recompute_memberships(db: Session, *, dry_run: bool) -> list[str]:
    """Phase 2. Returns every human-readable change made (or that would be
    made, under --dry-run), across every affected issuer."""
    all_changes: list[str] = []
    relevant_types = universe_classification_service.classification_relevant_evidence_types()
    issuer_ids = research_evidence_repository.list_issuer_ids_with_evidence_types(
        db, relevant_types
    )
    print(f"  {len(issuer_ids)} issuer(s) with classification-relevant evidence.", flush=True)

    for i, issuer_id in enumerate(issuer_ids, start=1):
        # Full per-issuer body inside the try — see the matching comment in
        # `_backfill_issuer_is_subject` for why (a connection drop on the
        # initial reads must isolate to this issuer, not crash the run).
        try:
            issuer = issuer_repository.get_issuer(db, issuer_id)
            if issuer is None:
                continue
            evidence = research_evidence_repository.list_evidence_by_issuer_and_types(
                db, issuer_id, relevant_types
            )
            if i % 25 == 0 or i == len(issuer_ids):
                print(f"  [{i}/{len(issuer_ids)}] ...", flush=True)
            effective = universe_classification_service.effective_reviews(db, evidence)
            expected = universe_classification_service.compute_expected_memberships(
                evidence, effective
            )
            if dry_run:
                # Read-only preview: compute what would change without
                # calling apply_correction (which writes).
                changes = _preview_changes(db, issuer_id, expected)
            else:
                changes = universe_classification_service.apply_correction(db, issuer_id, expected)
                db.commit()
            if changes:
                all_changes.extend(f"{issuer.legal_name}: {c}" for c in changes)
        except Exception as exc:  # noqa: BLE001 - per-issuer isolation
            db.rollback()
            print(f"  ERROR recomputing issuer {issuer_id}: {exc}")

    return all_changes


def _preview_changes(
    db: Session,
    issuer_id: UUID,
    expected: dict[str, tuple[VerificationStatus, ResearchEvidence]],
) -> list[str]:
    """Read-only mirror of `apply_correction`'s decision logic — no writes,
    used only for `--dry-run` reporting."""
    changes: list[str] = []
    for slug, name in universe_classification_service.evidence_driven_universe_slugs():
        collection = collection_repository.get_collection_by_slug(db, slug)
        if collection is None:
            continue
        current = collection_repository.get_membership(db, collection.id, issuer_id)
        target = expected.get(slug)
        if target is None:
            if current is not None and current.system_seeded:
                before = current.verification_status.value
                changes.append(f"{name}: would remove ({before} -> none)")
            continue
        status, _evidence = target
        if current is None:
            changes.append(f"{name}: would add ({status.value})")
        elif current.system_seeded and current.verification_status is not status:
            before = current.verification_status.value
            changes.append(f"{name}: would change ({before} -> {status.value})")
    return changes


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    try:
        llm = get_llm_provider(settings)
        print(f"AI evidence review: enabled (LLM_PROVIDER={settings.llm_provider}).")
    except LLMConfigurationError as exc:
        llm = None
        print(f"AI evidence review: disabled ({exc}).")

    if args.dry_run:
        print("DRY RUN — no writes will be made.\n")

    db = SessionLocal()
    try:
        universe_classification_service.seed_evidence_driven_universes(db)
        db.commit()

        print("Phase 1: backfilling issuer_is_subject for existing definitive-evidence alerts...")
        backfill_counts = _backfill_issuer_is_subject(db, llm, dry_run=args.dry_run)
        for outcome, count in sorted(backfill_counts.items()):
            print(f"  {outcome}: {count}")

        print("\nPhase 2: recomputing evidence-driven universe memberships...")
        changes = _recompute_memberships(db, dry_run=args.dry_run)
        print(f"  {len(changes)} membership change(s){' (dry run)' if args.dry_run else ''}:")
        for change in changes:
            print(f"    {change}")
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
