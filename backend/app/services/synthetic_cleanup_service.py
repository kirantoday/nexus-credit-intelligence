"""Safety-checked removal of synthetic demo data (PLAN.md Milestone 7.5.3
CFO-demo cleanup).

Two distinct, deliberately narrow operations:

- `remove_synthetic_securities_for_issuer`: deletes only `security` rows
  flagged `is_synthetic=True` for one issuer (plus their own exclusively-
  owned `provenance` rows). Never touches the issuer row itself, never
  touches a real security — safe to call on *any* issuer, real or
  synthetic, which is exactly the case CLAUDE.md's data-safety rule
  requires: "never delete a real issuer just because it has a synthetic
  security."

- `delete_synthetic_only_issuer`: the full cascade (capital structure
  positions, calculation/calculation_input lineage, securities, the
  issuer row itself, and every exclusively-owned provenance row) — but
  only when every safety condition holds: the issuer is flagged
  synthetic, and it has zero rows in any table that represents real
  canonical research history (SEC filings, research evidence, alerts,
  Research Universe membership, CourtListener/enrichment records,
  financial facts, AI call log). Any violation is a no-op, never a
  partial delete — this function never raises to signal "not eligible,"
  it returns a result the caller can inspect and report.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# Tables whose presence for an issuer means it is NOT synthetic-only —
# any real canonical research history at all disqualifies deletion.
_REAL_DEPENDENCY_TABLES: tuple[str, ...] = (
    "sec_filing",
    "research_evidence",
    "alert_event",
    "collection_membership",
    "court_docket",
    "issuer_enrichment_status",
    "financial_fact",
    "market_discovery_candidate",
    "ai_call_log",
)


@dataclass(frozen=True, slots=True)
class SyntheticIssuerDeletionResult:
    deleted: bool
    reason: str
    securities_deleted: int = 0
    capital_structure_positions_deleted: int = 0
    provenance_rows_deleted: int = 0
    calculations_deleted: int = 0


def remove_synthetic_securities_for_issuer(db: Session, issuer_id: UUID) -> int:
    """Deletes every `is_synthetic=True` security for `issuer_id` (and its
    own provenance row, if not referenced elsewhere) — never the issuer,
    never a real security. Returns the number of securities deleted."""
    rows = db.execute(
        text(
            "SELECT id, provenance_id FROM nexus.security "
            "WHERE issuer_id = :iid AND is_synthetic = true"
        ),
        {"iid": issuer_id},
    ).all()
    if not rows:
        return 0

    security_ids = [r.id for r in rows]
    provenance_ids = [r.provenance_id for r in rows]

    db.execute(text("DELETE FROM nexus.security WHERE id = ANY(:ids)"), {"ids": security_ids})

    # Only delete provenance rows nothing else still references.
    still_referenced = {
        r[0]
        for r in db.execute(
            text(
                "SELECT provenance_id FROM nexus.security WHERE provenance_id = ANY(:pids) "
                "UNION SELECT provenance_id FROM nexus.issuer WHERE provenance_id = ANY(:pids) "
                "UNION SELECT provenance_id FROM nexus.capital_structure_position "
                "WHERE provenance_id = ANY(:pids)"
            ),
            {"pids": provenance_ids},
        ).all()
    }
    deletable_provenance = [pid for pid in provenance_ids if pid not in still_referenced]
    if deletable_provenance:
        db.execute(
            text("DELETE FROM nexus.provenance WHERE id = ANY(:pids)"),
            {"pids": deletable_provenance},
        )

    return len(security_ids)


def delete_synthetic_only_issuer(db: Session, issuer_id: UUID) -> SyntheticIssuerDeletionResult:
    """All-or-nothing: deletes an issuer and everything exclusively owned
    by it only if it is confirmed synthetic-only with zero real canonical
    history. Never partially deletes."""
    issuer_row = db.execute(
        text("SELECT is_synthetic FROM nexus.issuer WHERE id = :iid"), {"iid": issuer_id}
    ).first()
    if issuer_row is None:
        return SyntheticIssuerDeletionResult(deleted=False, reason="issuer_not_found")
    if not issuer_row.is_synthetic:
        return SyntheticIssuerDeletionResult(deleted=False, reason="issuer_is_not_synthetic")

    for table in _REAL_DEPENDENCY_TABLES:
        n = db.execute(
            text(f"SELECT COUNT(*) FROM nexus.{table} WHERE issuer_id = :iid"), {"iid": issuer_id}
        ).scalar_one()
        if n > 0:
            return SyntheticIssuerDeletionResult(
                deleted=False, reason=f"has_real_dependency:{table}"
            )

    real_security = db.execute(
        text("SELECT COUNT(*) FROM nexus.security WHERE issuer_id = :iid AND is_synthetic = false"),
        {"iid": issuer_id},
    ).scalar_one()
    if real_security > 0:
        return SyntheticIssuerDeletionResult(deleted=False, reason="has_real_security")

    security_rows = db.execute(
        text("SELECT id, provenance_id FROM nexus.security WHERE issuer_id = :iid"),
        {"iid": issuer_id},
    ).all()
    csp_rows = db.execute(
        text(
            "SELECT id, provenance_id FROM nexus.capital_structure_position WHERE issuer_id = :iid"
        ),
        {"iid": issuer_id},
    ).all()
    issuer_provenance_id = db.execute(
        text("SELECT provenance_id FROM nexus.issuer WHERE id = :iid"), {"iid": issuer_id}
    ).scalar_one()

    all_provenance_ids = list(
        {issuer_provenance_id}
        | {r.provenance_id for r in security_rows}
        | {r.provenance_id for r in csp_rows}
    )
    calculation_ids = [
        r[0]
        for r in db.execute(
            text(
                "SELECT DISTINCT calculation_id FROM nexus.provenance "
                "WHERE id = ANY(:pids) AND calculation_id IS NOT NULL"
            ),
            {"pids": all_provenance_ids},
        ).all()
    ]

    db.execute(
        text("DELETE FROM nexus.calculation_input WHERE calculation_id = ANY(:cids)"),
        {"cids": calculation_ids},
    )
    db.execute(
        text("DELETE FROM nexus.capital_structure_position WHERE issuer_id = :iid"),
        {"iid": issuer_id},
    )
    db.execute(text("DELETE FROM nexus.security WHERE issuer_id = :iid"), {"iid": issuer_id})
    db.execute(text("DELETE FROM nexus.issuer WHERE id = :iid"), {"iid": issuer_id})
    db.execute(
        text("DELETE FROM nexus.provenance WHERE id = ANY(:pids)"), {"pids": all_provenance_ids}
    )
    db.execute(
        text("DELETE FROM nexus.calculation WHERE id = ANY(:cids)"), {"cids": calculation_ids}
    )

    return SyntheticIssuerDeletionResult(
        deleted=True,
        reason="deleted",
        securities_deleted=len(security_rows),
        capital_structure_positions_deleted=len(csp_rows),
        provenance_rows_deleted=len(all_provenance_ids),
        calculations_deleted=len(calculation_ids),
    )
