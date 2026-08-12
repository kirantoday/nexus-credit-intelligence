"""universal search vectors and indexes

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-12 11:47:03.246512

Milestone 12A (PLAN.md §4.13/§8, TD-003): adds one `search_vector`
(`tsvector`, `GENERATED ALWAYS AS ... STORED`) column + GIN index to each
of the seven tables Universal Search covers — `issuer`, `security`,
`alert_event`, `court_docket`, `court_docket_entry`, `collection`,
`research_note` — plus two `pg_trgm` GIN indexes (`issuer.legal_name`,
`security.description`) for typo-tolerant fuzzy matching, plus a plain
btree index on `court_docket.docket_number` (a human-readable exact-match
identifier that had no index before).

Resolves TD-003 in favor of per-table generated columns over a separate,
synced `search_document` table: a `GENERATED ALWAYS AS ... STORED` column
is maintained automatically by Postgres on every INSERT/UPDATE, so there is
no new write path for any of the many existing writers (SEC ingestion,
CourtListener sync, `research_note_service`, `watchlist_service`, ...) to
remember, and no drift risk. This project has zero triggers anywhere —
every side effect is explicit application code — and a synced
`search_document` table would have been the first exception to that.

Deliberately does **not** touch `research_evidence`, `research_note_version`,
`audit_event`, `docket_document`, or `sec_filing` — see
`app.repositories.search_repository`'s module docstring for why each is
excluded from Universal Search's schema footprint. No existing table's
behavior changes; every column is nullable and additive.

Live-caught during the first migration attempt: `research_note`'s original
generation expression used `concat_ws` to join six case fields, which
Postgres declares `STABLE`, not `IMMUTABLE` (it accepts variadic `any`
arguments, so its text output could in principle depend on session
settings for non-text types) — `GENERATED ALWAYS AS ... STORED` requires an
immutable expression and rejected it with `generation expression is not
immutable`. Postgres DDL is transactional, so the failed `ALTER TABLE`
rolled back cleanly with zero partial state (`alembic current` stayed at
`0015`, confirmed live before retrying). Fixed by replacing `concat_ws`
with plain `||` concatenation, which is immutable for `text`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alert_event",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(headline, '')), 'A') || "
                "setweight(to_tsvector('english', coalesce(explanation, '')), 'B') || "
                "setweight(to_tsvector('english', replace(coalesce(category, ''), '_', ' ')), 'C')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_alert_event_search_vector",
        "alert_event",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )
    op.add_column(
        "collection",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(name, '')), 'A') || "
                "setweight(to_tsvector('english', coalesce(description, '')), 'C')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_collection_search_vector",
        "collection",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )
    op.add_column(
        "court_docket",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(case_name, '')), 'A') || "
                "setweight(to_tsvector('english', coalesce(nature_of_suit, '')), 'C')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_court_docket_docket_number",
        "court_docket",
        ["docket_number"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_court_docket_search_vector",
        "court_docket",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )
    op.add_column(
        "court_docket_entry",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(description, '')), 'B')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_court_docket_entry_search_vector",
        "court_docket_entry",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )
    op.add_column(
        "issuer",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(legal_name, '')), 'A') || "
                "setweight(to_tsvector('english', coalesce(ticker, '')), 'A')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_issuer_legal_name_trgm",
        "issuer",
        ["legal_name"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
        postgresql_ops={"legal_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_issuer_search_vector",
        "issuer",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )
    op.add_column(
        "research_note",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('english', "
                "coalesce(bull_case, '') || ' ' || coalesce(base_case, '') || ' ' || "
                "coalesce(bear_case, '') || ' ' || coalesce(catalysts, '') || ' ' || "
                "coalesce(risks, '') || ' ' || coalesce(invalidation_conditions, '')"
                "), 'C')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_research_note_search_vector",
        "research_note",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )
    op.add_column(
        "security",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(description, '')), 'A')",
                persisted=True,
            ),
            nullable=True,
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_security_description_trgm",
        "security",
        ["description"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_security_search_vector",
        "security",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_security_search_vector",
        table_name="security",
        schema="nexus",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_security_description_trgm",
        table_name="security",
        schema="nexus",
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )
    op.drop_column("security", "search_vector", schema="nexus")
    op.drop_index(
        "ix_research_note_search_vector",
        table_name="research_note",
        schema="nexus",
        postgresql_using="gin",
    )
    op.drop_column("research_note", "search_vector", schema="nexus")
    op.drop_index(
        "ix_issuer_search_vector", table_name="issuer", schema="nexus", postgresql_using="gin"
    )
    op.drop_index(
        "ix_issuer_legal_name_trgm",
        table_name="issuer",
        schema="nexus",
        postgresql_using="gin",
        postgresql_ops={"legal_name": "gin_trgm_ops"},
    )
    op.drop_column("issuer", "search_vector", schema="nexus")
    op.drop_index(
        "ix_court_docket_entry_search_vector",
        table_name="court_docket_entry",
        schema="nexus",
        postgresql_using="gin",
    )
    op.drop_column("court_docket_entry", "search_vector", schema="nexus")
    op.drop_index(
        "ix_court_docket_search_vector",
        table_name="court_docket",
        schema="nexus",
        postgresql_using="gin",
    )
    op.drop_index("ix_court_docket_docket_number", table_name="court_docket", schema="nexus")
    op.drop_column("court_docket", "search_vector", schema="nexus")
    op.drop_index(
        "ix_collection_search_vector",
        table_name="collection",
        schema="nexus",
        postgresql_using="gin",
    )
    op.drop_column("collection", "search_vector", schema="nexus")
    op.drop_index(
        "ix_alert_event_search_vector",
        table_name="alert_event",
        schema="nexus",
        postgresql_using="gin",
    )
    op.drop_column("alert_event", "search_vector", schema="nexus")
