"""embedding job scheduling: retry_not_before, operator hold (DRAFT — not applied)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-02

**DRAFT — inert and unapplied.** Lives in `alembic/drafts/`, which Alembic does
not scan, so `alembic upgrade head` cannot reach it.

**Why a separate revision.** Local evidence cannot show whether draft 0022 was
ever applied in any environment (no live check is authorized, and the drafts
README only records intent). A revision that may have run must never be edited,
so these changes are a new revision on top of 0022. If the owner later confirms
that 0022 has never been applied anywhere, folding this into 0022 is a separate
decision; nothing here assumes it.

**Activation order (when separately approved).** Move 0021, 0022 and 0023
into `alembic/versions/` together, in that order, keeping their revision ids,
re-run the offline checks, then apply one revision at a time. 0023 requires
0022's `nexus.document_embedding_job` to exist.

Changes to `nexus.document_embedding_job` only (no other table, no extension,
no vector type):

- `retry_not_before timestamptz NULL` — earliest claim time; only while
  `pending`. `NULL` means no delay. A value equal to "now" is due.
- `provider_wide boolean NOT NULL DEFAULT false` — the delay or hold applies to
  every job for the same provider and model (rate limits, credentials, quota).
- `hold_reason text NULL`, `held_at timestamptz NULL` — set when a job is
  `held`; kept after release as history.
- `released_at timestamptz NULL`, `released_by text NULL` — the last operator
  release; `released_by` is an asserted, unverified name.
- New status value `held` (operator hold). The status CHECK is replaced; the
  "one active job per target" partial unique index is replaced so that a held
  job still owns its slot (re-enqueueing must not bypass a hold).
- CHECKs: a held job has a reason; a delay exists only on a pending job;
  `provider_wide` only on pending/held jobs.
- A partial index for the provider-wide blocker lookup used by the claim query.

**Existing rows.** New nullable columns are NULL and `provider_wide` is false,
so every existing row satisfies the new CHECKs unchanged; no backfill is
needed. Adding a constant-default NOT NULL column and the CHECK validation are
expected to be quick on this small table but take brief exclusive locks;
duration and lock behavior are **unverified** until a live preflight.

**Downgrade.** Dropping the columns discards hold and release history and any
pending delays (a data loss). Held jobs cannot be represented in the old
status CHECK, so the downgrade **aborts** if any `held` row exists rather than
silently turning holds into claimable work. Rollback behavior is unverified
until tested against a real database.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "document_embedding_job"
_OLD_STATUS = "'pending', 'processing', 'completed', 'failed', 'blocked_ineligible'"
_NEW_STATUS = "'pending', 'processing', 'completed', 'failed', 'blocked_ineligible', 'held'"


def upgrade() -> None:
    op.add_column(
        _TABLE, sa.Column("retry_not_before", sa.DateTime(timezone=True), nullable=True),
        schema="nexus",
    )
    op.add_column(
        _TABLE,
        sa.Column("provider_wide", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="nexus",
    )
    op.add_column(_TABLE, sa.Column("hold_reason", sa.Text(), nullable=True), schema="nexus")
    op.add_column(
        _TABLE, sa.Column("held_at", sa.DateTime(timezone=True), nullable=True), schema="nexus"
    )
    op.add_column(
        _TABLE, sa.Column("released_at", sa.DateTime(timezone=True), nullable=True), schema="nexus"
    )
    op.add_column(_TABLE, sa.Column("released_by", sa.Text(), nullable=True), schema="nexus")

    op.drop_constraint("ck_document_embedding_job_status", _TABLE, type_="check", schema="nexus")
    op.create_check_constraint(
        "ck_document_embedding_job_status", _TABLE, f"status IN ({_NEW_STATUS})", schema="nexus"
    )
    op.create_check_constraint(
        "ck_document_embedding_job_held_has_reason",
        _TABLE,
        "status <> 'held' OR hold_reason IS NOT NULL",
        schema="nexus",
    )
    op.create_check_constraint(
        "ck_document_embedding_job_delay_only_when_pending",
        _TABLE,
        "retry_not_before IS NULL OR status = 'pending'",
        schema="nexus",
    )
    op.create_check_constraint(
        "ck_document_embedding_job_provider_wide_only_pending_or_held",
        _TABLE,
        "NOT provider_wide OR status IN ('pending', 'held')",
        schema="nexus",
    )

    op.drop_index(
        "ux_document_embedding_job_one_active_per_target",
        table_name=_TABLE,
        schema="nexus",
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )
    op.create_index(
        "ux_document_embedding_job_one_active_per_target",
        _TABLE,
        ["document_extraction_id", "embedding_model", "embedding_model_version"],
        unique=True,
        schema="nexus",
        postgresql_where=sa.text("status IN ('pending', 'processing', 'held')"),
    )
    op.create_index(
        "ix_document_embedding_job_provider_wide",
        _TABLE,
        ["embedding_provider", "embedding_model"],
        unique=False,
        schema="nexus",
        postgresql_where=sa.text("provider_wide AND status IN ('pending', 'held')"),
    )


def downgrade() -> None:
    # Held jobs cannot be represented by the old status CHECK, and converting
    # them to claimable work would silently remove an operator hold: refuse.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM nexus.document_embedding_job WHERE status = 'held') THEN "
        "RAISE EXCEPTION 'cannot downgrade 0023: held embedding jobs exist; release or "
        "resolve them first'; "
        "END IF; END $$"
    )

    op.drop_index(
        "ix_document_embedding_job_provider_wide",
        table_name=_TABLE,
        schema="nexus",
        postgresql_where=sa.text("provider_wide AND status IN ('pending', 'held')"),
    )
    op.drop_index(
        "ux_document_embedding_job_one_active_per_target",
        table_name=_TABLE,
        schema="nexus",
        postgresql_where=sa.text("status IN ('pending', 'processing', 'held')"),
    )
    op.create_index(
        "ux_document_embedding_job_one_active_per_target",
        _TABLE,
        ["document_extraction_id", "embedding_model", "embedding_model_version"],
        unique=True,
        schema="nexus",
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )

    op.drop_constraint(
        "ck_document_embedding_job_provider_wide_only_pending_or_held",
        _TABLE,
        type_="check",
        schema="nexus",
    )
    op.drop_constraint(
        "ck_document_embedding_job_delay_only_when_pending", _TABLE, type_="check", schema="nexus"
    )
    op.drop_constraint(
        "ck_document_embedding_job_held_has_reason", _TABLE, type_="check", schema="nexus"
    )
    op.drop_constraint("ck_document_embedding_job_status", _TABLE, type_="check", schema="nexus")
    op.create_check_constraint(
        "ck_document_embedding_job_status", _TABLE, f"status IN ({_OLD_STATUS})", schema="nexus"
    )

    for column in (
        "released_by",
        "released_at",
        "held_at",
        "hold_reason",
        "provider_wide",
        "retry_not_before",
    ):
        op.drop_column(_TABLE, column, schema="nexus")
