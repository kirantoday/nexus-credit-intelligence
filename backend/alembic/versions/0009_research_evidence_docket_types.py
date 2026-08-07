"""research evidence docket types

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-06 20:55:12.034801

Corrective migration: migration 0008 extended `app.core.types.EvidenceType`
with six docket-specific values (`plan_confirmed`, `case_dismissed`,
`case_converted`, `trustee_appointed`, `claims_bar_date_set`,
`relief_from_stay_motion`) but `alembic revision --autogenerate` never
emitted the corresponding `ck_research_evidence_type` change — Alembic's
`checkconstraint_byname` plugin compares CHECK constraints by name only, not
by their SQL body, so a same-named constraint whose expression changed is
silently treated as unchanged. Caught live: a real docket-entry sync raised
`psycopg.errors.CheckViolation` inserting `relief_from_stay_motion` (see
BUILD_LOG.md). This migration drops and recreates the constraint with the
full, current `EvidenceType` list — the fix belongs in a new migration, not
a rewrite of the already-applied 0008.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_EVIDENCE_TYPES = (
    "bankruptcy_or_receivership",
    "chapter_11",
    "chapter_7",
    "default_or_missed_payment",
    "covenant_breach",
    "debt_acceleration",
    "going_concern",
    "substantial_doubt",
    "liquidity_warning",
    "restructuring_advisor",
    "restructuring_support_agreement",
    "exchange_offer",
    "liability_management_transaction",
    "debt_amendment",
    "maturity_extension",
    "refinancing",
    "dip_financing",
    "emergency_financing",
    "material_asset_sale",
    "delisting_notice",
    "workforce_reduction",
    "facility_closure",
    "material_impairment",
    "auditor_resignation",
    "adverse_audit_development",
    "strategic_alternatives",
)

_NEW_EVIDENCE_TYPES = _OLD_EVIDENCE_TYPES + (
    "plan_confirmed",
    "case_dismissed",
    "case_converted",
    "trustee_appointed",
    "claims_bar_date_set",
    "relief_from_stay_motion",
)


def _check_sql(values: tuple[str, ...]) -> str:
    value_list = ", ".join(f"'{v}'" for v in values)
    return f"evidence_type IN ({value_list})"


def upgrade() -> None:
    op.drop_constraint(
        "ck_research_evidence_type", "research_evidence", schema="nexus", type_="check"
    )
    op.create_check_constraint(
        "ck_research_evidence_type",
        "research_evidence",
        _check_sql(_NEW_EVIDENCE_TYPES),
        schema="nexus",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_research_evidence_type", "research_evidence", schema="nexus", type_="check"
    )
    op.create_check_constraint(
        "ck_research_evidence_type",
        "research_evidence",
        _check_sql(_OLD_EVIDENCE_TYPES),
        schema="nexus",
    )
