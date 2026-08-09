"""drop morning_brief_view

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-09 00:00:00.000000

Milestone 7.5.2's second correction (PLAN.md): the Morning Research
Brief's comparison window is now derived entirely from canonical
successful daily-run data plus calendar business-day arithmetic — never
from when the page was viewed. `morning_brief_view` (added in migration
`0012` for exactly that now-abandoned page-view-based boundary) has no
remaining reader anywhere in the codebase; nothing else was ever built to
consume it (no "unread" badge, no read-state UI). Removed rather than
carried forward as unused architecture, per explicit instruction. Its
removal also means `POST /api/morning-brief/view` (the only writer) no
longer exists, so TD-019's live-caught, never-conclusively-root-caused
intermittent `503` on that specific endpoint cannot recur — the endpoint
itself is gone, not merely worked around; TD-019 stays recorded in
PLAN.md as a closed-by-removal historical finding, not silently deleted
from the record.

`collection_membership.updated_at` (also added in migration `0012`) is
untouched — still genuinely needed for Research-Universe-membership
"upgraded" detection, unrelated to the page-view mechanism being removed
here.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("morning_brief_view", schema="nexus")


def downgrade() -> None:
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
