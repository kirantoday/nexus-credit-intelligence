"""enable pgvector and pg_trgm extensions

Revision ID: 0001
Revises:
Create Date: 2026-08-04

This is Version 1's initial migration. It intentionally creates no tables
(Milestone 1 has no canonical domain models yet, per PLAN.md's build order) —
it exists to prove the Alembic -> DIRECT_DATABASE_URL -> Supabase path works
end-to-end, and to enable the two Postgres extensions the frozen architecture
depends on: pgvector (gated embeddings, PLAN.md section 4.9) and pg_trgm
(fuzzy search, PLAN.md section 4.13).
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
