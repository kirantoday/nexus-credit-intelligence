"""morning_brief_view and collection_membership.updated_at

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-09 00:00:00.000000

Milestone 7.5.2 correction (PLAN.md): the Morning Research Brief's default
window moves from a pipeline-run boundary to a user-relative one — "what
changed since this was last viewed" — which needs somewhere to persist "the
brief was viewed" as its own concept, distinct from any `filing_monitor_run`/
`market_discovery_run` watermark. `morning_brief_view` is a single shared,
append-only timeline (not per-user): Nexus has no authentication/session
infrastructure yet (TD-002, open), so per-user state would have to be faked;
the real per-user requirement is recorded as new Technical Debt instead.

`collection_membership.updated_at` is added so an *upgrade* to an existing
membership (e.g. `partial` -> `verified`, written by
`upgrade_membership_verification`/`set_membership_verification`) is
distinguishable from a brand-new membership (`added_at`) — needed to surface
"an issuer's Research Universe membership changed materially" in the brief.
Existing rows are backfilled to `updated_at = added_at` (never having been
upgraded since creation, as far as this column's history goes) rather than
left at this migration's own execution time — the naive
`ADD COLUMN ... DEFAULT now()` behavior, which would otherwise make every
one of the ~540+ pre-existing memberships appear to have "just changed" the
first time the corrected brief boundary logic runs.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "morning_brief_view",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "viewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.add_column(
        "collection_membership",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema="nexus",
    )
    op.execute("UPDATE nexus.collection_membership SET updated_at = added_at")


def downgrade() -> None:
    op.drop_column("collection_membership", "updated_at", schema="nexus")
    op.drop_table("morning_brief_view", schema="nexus")
