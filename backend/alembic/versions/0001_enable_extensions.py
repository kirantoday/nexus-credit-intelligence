"""create nexus schema, enable pgvector and pg_trgm extensions

Revision ID: 0001
Revises:
Create Date: 2026-08-04

This is Version 1's initial migration. It intentionally creates no tables
(Milestone 1 has no canonical domain models yet, per PLAN.md's build order) —
it exists to prove the Alembic -> DIRECT_DATABASE_URL -> Supabase path works
end-to-end, create the `nexus` schema that isolates this application inside a
Supabase project shared with another application, and enable the two Postgres
extensions the frozen architecture depends on: pgvector (gated embeddings,
PLAN.md section 4.9) and pg_trgm (fuzzy search, PLAN.md section 4.13).

Extensions are database-wide, not schema-scoped, and may already be relied on
by the other application sharing this database — this migration only ever
creates them (CREATE EXTENSION IF NOT EXISTS) and never drops, downgrades, or
relocates them, including on downgrade.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS nexus")
    # WITH SCHEMA public is explicit, not incidental: the Nexus app/migration
    # connection's search_path is "nexus, public" (see app/db/session.py,
    # alembic/env.py), so an unqualified CREATE EXTENSION would otherwise
    # install into whichever schema resolves first on that search_path —
    # i.e. nexus — rather than the shared, database-wide location these
    # extensions actually belong in (matching where `vector` already lived
    # on this shared Supabase project before Nexus's first migration ran).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")


def downgrade() -> None:
    # vector/pg_trgm are shared, database-wide resources that may be in use by
    # the other application on this Supabase project — never dropped here.
    # By the time this migration's downgrade runs, every later Nexus migration
    # has already dropped its own nexus-schema objects, so the schema itself is
    # empty; no CASCADE is used or needed.
    op.execute("DROP SCHEMA IF EXISTS nexus")
