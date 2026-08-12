"""Seed script: one Demo Research Note on Trinseo PLC, showing three real,
dated versions of an analyst thesis evolving with Trinseo's actual,
already-ingested distress timeline (PLAN.md 24.12; Milestone 10A).

    python -m app.scripts.seed_demo_research_note

Every fact this note references — covenant stress (2026-02-17), explicit
going-concern doubt (2026-03-13), the exchange-offer/NYSE-delisting
restructuring stretch (2026-03-20 through 2026-04-27), and the Chapter 11
petition (2026-05-26) plus DIP financing (2026-06-01) — is a real,
already-ingested `alert_event` row from Trinseo's live SEC EDGAR filing
history (query verified live against the `nexus` schema before writing this
script). The analyst *conclusions* (thesis status, conviction, bull/base/
bear case, catalysts, risks, invalidation conditions) are this script's own
construction, written the way a real analyst plausibly would given that
evidence — never fabricated as though a real Stonehill analyst wrote them.
The note is created with `is_demo=True` and a "Demo Research Note:" title
prefix so the UI always renders it as clearly synthetic provenance, per the
CFO-demo requirement to never blur real evidence with a fabricated verdict.

Built through `research_note_service.create_note`/`update_note` — the same
service path a real analyst's UI action uses, not raw SQL or a script that
bypasses versioning/audit-event writing. Each `update_note` call below is a
material edit, so it produces a real, standalone `research_note_version`
snapshot (versions 1 -> 2 -> 3) and a real `audit_event` row, exactly as if
an analyst had actually made three separate edits over time.

Idempotent — safe to re-run: if a demo note already exists for this issuer,
it is left untouched and the script exits without creating a duplicate.
"""

from __future__ import annotations

import sys
from uuid import UUID

from app.core.types import AccessClassification, Conviction, ThesisStatus
from app.db.session import SessionLocal
from app.domain.research import EvidenceRef, ResearchNoteCreate, ResearchNoteUpdate
from app.repositories import issuer_repository
from app.services import research_note_service

TRINSEO_ISSUER_ID = UUID("67d65abe-76be-4171-a885-ad6e38e548f7")
DEMO_TITLE = "Demo Research Note: Trinseo PLC — Covenant Stress to Chapter 11"
DEMO_AUTHOR = "Nexus Demo"

# Real alert_event ids from Trinseo's live-ingested distress timeline
# (queried live against the nexus schema; see module docstring).
_EV_COVENANT_BREACH_FEB17 = UUID("74024a4a-6b73-4132-8bd7-185437e67877")
_EV_GOING_CONCERN_MAR13 = UUID("1e02dd34-8816-44e3-87e5-59e4caf84623")
_EV_EXCHANGE_OFFER_MAR20 = UUID("b7c6263e-db10-4daa-878e-52227cb1a73a")
_EV_DELISTING_APR13 = UUID("2bca0626-44eb-4f7e-aea8-b609de2e6b5f")
_EV_DELISTING_APR27 = UUID("e7142f7c-c1a4-4326-8e70-ff337a08af4b")
_EV_CH11_PLANS_MAY14 = UUID("f2b295f0-4b8b-4dfd-b891-8c7308a6a735")
_EV_CH11_FILED_MAY26 = UUID("691b5ca5-15f1-4583-8bbf-8996eac80f29")
_EV_DIP_FINANCING_JUN01 = UUID("67668a76-375a-4534-ab80-43cb0b43e1ef")


def main() -> int:
    if SessionLocal is None:
        print("ERROR: DATABASE_URL is not configured.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        issuer = issuer_repository.get_issuer(db, TRINSEO_ISSUER_ID)
        if issuer is None:
            print(f"Issuer {TRINSEO_ISSUER_ID} (expected Trinseo PLC) not found — aborting.")
            return 1

        existing = research_note_service.list_notes_for_issuer(
            db, TRINSEO_ISSUER_ID, include_archived=True
        )
        if any(n.is_demo for n in existing):
            print("Demo Research Note for Trinseo PLC already exists — skipping (idempotent).")
            return 0

        # Version 1 (as of ~2026-02-17 -> 2026-03-13): covenant stress just
        # emerging, before going-concern doubt was explicit. Low conviction —
        # genuinely uncertain at this point whether this resolves via waiver
        # or deteriorates further.
        note = research_note_service.create_note(
            db,
            ResearchNoteCreate(
                issuer_id=TRINSEO_ISSUER_ID,
                title=DEMO_TITLE,
                thesis_status=ThesisStatus.MONITORING,
                conviction=Conviction.LOW,
                bull_case=(
                    "Trinseo secures a covenant waiver or amendment from lenders, buying time "
                    "to stabilize EBITDA and refinance on more favorable terms before any "
                    "payment default."
                ),
                base_case=(
                    "Covenant stress persists through the next reporting cycle; management "
                    "pursues a negotiated amendment while continuing to disclose default and "
                    "restructuring risk in SEC filings."
                ),
                bear_case=(
                    "Covenant breaches compound into a formal going-concern qualification and "
                    "an eventual restructuring or bankruptcy filing."
                ),
                catalysts=(
                    "Q1 10-Q covenant compliance disclosure; any lender waiver or amendment "
                    "announcement."
                ),
                risks="Continued EBITDA deterioration; further covenant breach disclosures.",
                invalidation_conditions=(
                    "An explicit going-concern qualification is disclosed, or Trinseo engages a "
                    "restructuring advisor / enters exchange-offer discussions with lenders."
                ),
                evidence_refs=[
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_COVENANT_BREACH_FEB17,
                        label="8-K: default and debt restructuring signals (2026-02-17)",
                    ),
                ],
                access_classification=AccessClassification.STANDARD,
                author_user_id=DEMO_AUTHOR,
                is_demo=True,
            ),
        )
        db.commit()
        print(f"Created demo note {note.id} — version 1 (Covenant Stress).")

        # Version 2 (as of ~2026-03-13 -> 2026-04-27): the invalidation
        # condition from v1 was met — going-concern doubt is now explicit,
        # and Trinseo is in active exchange-offer/restructuring discussions
        # with an NYSE delisting layered on top. Thesis moves to active
        # monitoring of a live restructuring, conviction rises to medium.
        updated_v2 = research_note_service.update_note(
            db,
            note.id,
            ResearchNoteUpdate(
                thesis_status=ThesisStatus.ACTIVE,
                conviction=Conviction.MEDIUM,
                bull_case=(
                    "An out-of-court exchange offer or credit agreement amendment resolves the "
                    "capital structure without a formal bankruptcy filing."
                ),
                base_case=(
                    "Trinseo pursues a negotiated liability-management transaction against a "
                    "backdrop of explicit going-concern doubt and NYSE delisting; a Chapter 11 "
                    "filing becomes an increasingly plausible near-term outcome rather than a "
                    "tail risk."
                ),
                bear_case=(
                    "Restructuring discussions fail to produce an out-of-court resolution and "
                    "Trinseo files for Chapter 11 protection."
                ),
                catalysts=(
                    "Outcome of active exchange-offer discussions; any restructuring support "
                    "agreement (RSA) announcement; NYSE delisting finalization."
                ),
                risks=(
                    "Going-concern doubt is now explicit (10-K, 2026-03-13); NYSE delisting in "
                    "progress; cross-default risk across the capital structure."
                ),
                invalidation_conditions="Trinseo files a voluntary Chapter 11 petition.",
                evidence_refs=[
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_COVENANT_BREACH_FEB17,
                        label="8-K: default and debt restructuring signals (2026-02-17)",
                    ),
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_GOING_CONCERN_MAR13,
                        label="10-K: explicit going-concern doubt (2026-03-13)",
                    ),
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_EXCHANGE_OFFER_MAR20,
                        label="8-K: capital structure review / waiver discussions (2026-03-20)",
                    ),
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_DELISTING_APR13,
                        label="8-K: NYSE delisting and capital structure discussions (2026-04-13)",
                    ),
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_DELISTING_APR27,
                        label="10-K/A: NYSE delisting confirmed (2026-04-27)",
                    ),
                ],
                edited_by=DEMO_AUTHOR,
            ),
        )
        db.commit()
        assert updated_v2 is not None
        print(f"Updated demo note {note.id} — version 2 (Going Concern / Restructuring).")

        # Version 3 (as of 2026-05-26 Chapter 11 filing onward): the v2
        # invalidation condition was met — Trinseo filed a voluntary
        # Chapter 11 petition under a prepackaged plan. Thesis is marked
        # INVALIDATED (the original covenant-stress-resolves-out-of-court
        # thesis did not hold) with high conviction in that outcome, now
        # confirmed by DIP financing and continued Chapter 11 proceedings.
        updated_v3 = research_note_service.update_note(
            db,
            note.id,
            ResearchNoteUpdate(
                thesis_status=ThesisStatus.INVALIDATED,
                conviction=Conviction.HIGH,
                bull_case=(
                    "Prepackaged Chapter 11 plan confirms quickly with minimal value leakage to "
                    "existing capital structure holders relative to the pre-petition RSA terms."
                ),
                base_case=(
                    "Trinseo proceeds through Chapter 11 under its prepackaged plan of "
                    "reorganization, funded by debtor-in-possession financing, emerging with a "
                    "delevered capital structure."
                ),
                bear_case=(
                    "Chapter 11 proceedings extend beyond the prepackaged timeline or DIP "
                    "financing terms erode recoveries for existing holders."
                ),
                catalysts="Plan confirmation hearing; DIP-to-exit financing conversion.",
                risks=(
                    "Chapter 11 execution risk; DIP financing terms; going-concern doubt remains "
                    "open as of the most recent 10-Q (2026-08-06)."
                ),
                invalidation_conditions=(
                    "Already met — see thesis status. Retained here as the historical record of "
                    "what would have proven the original thesis wrong."
                ),
                evidence_refs=[
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_CH11_PLANS_MAY14,
                        label="8-K: Chapter 11 filing plans confirmed (2026-05-14)",
                    ),
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_CH11_FILED_MAY26,
                        label="Voluntary Chapter 11 petition filed, prepackaged plan (2026-05-26)",
                    ),
                    EvidenceRef(
                        entity_table="alert_event",
                        entity_id=_EV_DIP_FINANCING_JUN01,
                        label=(
                            "Filing confirms Chapter 11 proceedings and DIP financing "
                            "(2026-06-01)"
                        ),
                    ),
                ],
                edited_by=DEMO_AUTHOR,
            ),
        )
        db.commit()
        assert updated_v3 is not None
        print(f"Updated demo note {note.id} — version 3 (Chapter 11 / Invalidated).")
        print(
            f"Demo Research Note complete: {note.id} "
            f"(current version {updated_v3.current_version_number})."
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
