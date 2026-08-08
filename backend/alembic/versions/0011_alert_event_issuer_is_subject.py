"""alert_event issuer_is_subject

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-08 00:00:00.000000

Milestone 7.5.1 (PLAN.md): adds `alert_event.issuer_is_subject` (nullable
boolean). Root-caused during Milestone 7.5.1's audit: `research_evidence`'s
Layer-1 deterministic severity has no concept of *whose* event a matched
phrase describes — "Chapter 11" fires identically whether the excerpt
describes the issuer's own bankruptcy or a director's former employer's,
a customer's, or a peer company's. The Layer 2 AI review already makes
this exact distinction correctly in its prose (live-verified: BlackSky
Technology's alert already reads "relates to a director's prior company,
not BlackSky"), but that judgment was never captured as structured data,
so `universe_classification_service` (which only ever read
`research_evidence.severity`) could not use it. `NULL` means "no AI review
performed" (deterministic-only alert, or pre-migration historical row) —
treated as "unknown," not as `false`, so existing deterministic-fallback
behavior is unaffected. No other table changed; autogenerate detected zero
drift elsewhere.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alert_event",
        sa.Column("issuer_is_subject", sa.Boolean(), nullable=True),
        schema="nexus",
    )


def downgrade() -> None:
    op.drop_column("alert_event", "issuer_is_subject", schema="nexus")
