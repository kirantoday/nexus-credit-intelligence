"""research document search vector

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-12 23:00:00.000000

Milestone 10B-5 (PLAN.md 4.13/8; extends Milestone 12A's Universal Search):
adds one `search_vector` (`tsvector`, `GENERATED ALWAYS AS ... STORED`)
column + GIN index to `research_document`, matching the exact pattern
Migration 0016 already established for every other searchable entity —
`title` (weight A), `document_type` (weight C, underscores replaced with
spaces so "credit agreement" matches `credit_agreement`, mirroring
`alert_event.category`'s identical treatment), and `description`
(weight C, mirroring `research_note`'s case fields / `collection.
description`).

Deliberately does **not** include `extracted_text` — no PDF extraction
exists anywhere in this codebase yet (out of scope for Milestone 10B); that
column stays `NULL` and is not referenced by this generated expression at
all, so this migration can never be mistaken for implying document-content
search exists. Plain `||` concatenation, not `concat_ws` — see Migration
0016's docstring for why (`concat_ws` is STABLE, not IMMUTABLE, and
`GENERATED ALWAYS AS ... STORED` requires an immutable expression).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "research_document",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('english', "
                "replace(coalesce(document_type, ''), '_', ' ')), 'C') || "
                "setweight(to_tsvector('english', coalesce(description, '')), 'C')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_research_document_search_vector",
        "research_document",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_document_search_vector", table_name="research_document", schema="nexus"
    )
    op.drop_column("research_document", "search_vector", schema="nexus")
