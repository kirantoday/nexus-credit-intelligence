"""ai call log

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-09 12:00:00.000000

Milestone 7.5.3's AI cost-control correction (PLAN.md): before this,
Nexus's evidence-review AI usage had zero observability — no record of
which model was called, how many tokens it used, or what it likely cost.
`ai_call_log` records one row per real Anthropic API request (never per
skipped/deterministic decision — see `app.ai.model_router`), so a
discovery/backfill run can report exact AI usage/cost instead of a guess.
`discovery_run_id`/`filing_monitor_run_id` are both nullable FKs to the two
existing run tables (mirrors ADR-018's nullable-per-provider-FK pattern,
never both set for one row) — a call made outside either run context (the
one-off `app.scripts.reclassify_system_universes` maintenance script)
leaves both null. No existing table changed.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_call_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("discovery_run_id", sa.UUID(), nullable=True),
        sa.Column("filing_monitor_run_id", sa.UUID(), nullable=True),
        sa.Column("issuer_id", sa.UUID(), nullable=True),
        sa.Column("bundle_key", sa.Text(), nullable=True),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("routing_reason", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_classification", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('evidence_review', 'reclassify_issuer_is_subject')",
            name="ck_ai_call_log_operation",
        ),
        sa.CheckConstraint(
            "route IN ('deterministic', 'haiku', 'sonnet')",
            name="ck_ai_call_log_route",
        ),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["nexus.market_discovery_run.id"]),
        sa.ForeignKeyConstraint(["filing_monitor_run_id"], ["nexus.filing_monitor_run.id"]),
        sa.ForeignKeyConstraint(["issuer_id"], ["nexus.issuer.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_ai_call_log_discovery_run_id",
        "ai_call_log",
        ["discovery_run_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_ai_call_log_filing_monitor_run_id",
        "ai_call_log",
        ["filing_monitor_run_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_ai_call_log_issuer_id",
        "ai_call_log",
        ["issuer_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_ai_call_log_bundle_key",
        "ai_call_log",
        ["bundle_key"],
        unique=False,
        schema="nexus",
    )


def downgrade() -> None:
    op.drop_index("ix_ai_call_log_bundle_key", table_name="ai_call_log", schema="nexus")
    op.drop_index("ix_ai_call_log_issuer_id", table_name="ai_call_log", schema="nexus")
    op.drop_index("ix_ai_call_log_filing_monitor_run_id", table_name="ai_call_log", schema="nexus")
    op.drop_index("ix_ai_call_log_discovery_run_id", table_name="ai_call_log", schema="nexus")
    op.drop_table("ai_call_log", schema="nexus")
