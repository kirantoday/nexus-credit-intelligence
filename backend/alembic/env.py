"""Alembic environment.

Uses DIRECT_DATABASE_URL (non-pooled Supabase connection) for migrations, per
PLAN.md's Supabase/database stack decision — DATABASE_URL (pooled) is for the
running app only.

This Supabase project is shared with another application. Nexus owns only the
`nexus` Postgres schema (`app/db/base.py`'s NEXUS_SCHEMA): the Alembic version
table lives at `nexus.alembic_version` (version_table_schema), and autogenerate
is restricted to the `nexus` schema via `include_name` so it never proposes a
diff against — or migration for — objects belonging to the other application.
"""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from logging.config import fileConfig
from typing import Literal

from sqlalchemy import engine_from_config, pool, text

from alembic import context

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# app.models's __init__.py imports every model module so Base.metadata is
# fully populated before autogenerate compares against it (also the fix for
# a real NoReferencedTableError bug found in Milestone 3 — see that module's
# docstring).
import app.models  # noqa: E402, F401
from app.config import get_settings  # noqa: E402
from app.db.base import NEXUS_SCHEMA, Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_settings = get_settings()
_db_url = _settings.direct_database_url or _settings.database_url
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

target_metadata = Base.metadata


_IncludeNameType = Literal[
    "schema",
    "table",
    "column",
    "index",
    "unique_constraint",
    "foreign_key_constraint",
    "check_constraint",
]


def include_name(
    name: str | None,
    type_: _IncludeNameType,
    parent_names: MutableMapping[
        Literal["schema_name", "table_name", "schema_qualified_table_name"], str | None
    ],
) -> bool:
    """Restrict reflection/autogenerate to the nexus schema.

    Without this, `include_schemas=True` would reflect every schema in the
    shared database — including the other application's — and autogenerate
    could propose migrations against tables Nexus doesn't own.
    """
    if type_ == "schema":
        return name == NEXUS_SCHEMA
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema=NEXUS_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Deliberately NOT setting search_path=nexus,public here (unlike
    # app/db/session.py's app engine). Doing so once made "nexus" this
    # connection's *default* schema, which Alembic's reflection represents
    # internally as schema=None — a real bug found during Milestone 3: with
    # pre-existing nexus tables already live, autogenerate reflected them
    # under schema=None, include_name's `name == NEXUS_SCHEMA` check excluded
    # that None, and autogenerate concluded every existing table was missing
    # and proposed recreating them all. Every migration operation here is
    # already schema-qualified explicitly (schema="nexus" on every op.*
    # call), so this was pure defense-in-depth with no correctness need —
    # removing it is the actual fix, not a workaround.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Alembic creates its version table (nexus.alembic_version) before
        # running any migration, including migration 0001 — which is what
        # actually owns creating the nexus schema. Without this, the very
        # first `alembic upgrade head` on a fresh database fails with
        # "schema nexus does not exist" before 0001 ever runs. Idempotent, and
        # migration 0001 still issues its own CREATE SCHEMA IF NOT EXISTS so
        # the migration file remains correct/self-contained on its own.
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {NEXUS_SCHEMA}"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema=NEXUS_SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
