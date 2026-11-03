"""Opt-in guard for embedding integration tests (Milestone 10D.2).

The project's integration tests run against the real, **shared** Supabase
`nexus` schema inside a rolled-back transaction (the only policy-compliant
live target — CLAUDE.md, ADR-013). That is not risk-free: a rolled-back
transaction still takes locks and exercises a shared database. These
tests additionally touch tables that exist only after the 10D migrations
are applied, so they must never run by accident just because a developer's
`.env` happens to contain `DATABASE_URL`.

A test using `embedding_db_session` runs only when **all** of these hold,
and is otherwise skipped (never failed):

1. `NEXUS_ALLOW_EMBEDDING_DB_TESTS=1` is set explicitly in the environment;
2. `DATABASE_URL` is configured (the normal integration gate); and
3. the 10D tables are actually present (migrations 0021/0022 were applied
   through the separately approved plan).

The opt-in is checked **before** the `db_session` fixture is requested, so
a run without it never opens a database connection at all.

Nothing in the 10D.2 local implementation sets this variable or applies a
migration.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

OPT_IN_ENV = "NEXUS_ALLOW_EMBEDDING_DB_TESTS"
_REQUIRED_TABLES = (
    "public_document_approval",
    "document_embedding_job",
    "document_chunk_embedding",
    "embedding_call_log",
)


@pytest.fixture
def embedding_db_session(request: pytest.FixtureRequest) -> Iterator[Session]:
    if os.environ.get(OPT_IN_ENV) != "1":
        pytest.skip(f"{OPT_IN_ENV}=1 not set; embedding DB tests never run implicitly")
    db_session: Session = request.getfixturevalue("db_session")
    for table in _REQUIRED_TABLES:
        found = db_session.execute(
            text("SELECT to_regclass(:name)"), {"name": f"nexus.{table}"}
        ).scalar_one()
        if found is None:
            pytest.skip(f"nexus.{table} does not exist; 10D migrations are not applied")
    yield db_session
