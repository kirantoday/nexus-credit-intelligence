"""Fixtures for integration tests that hit the real, shared Supabase project.

No SQLite anywhere, ever (CLAUDE.md) — integration tests for repositories run
against the live `nexus` schema when DATABASE_URL is configured, and are
skipped (not failed) otherwise, matching the KI-001 gating pattern already
established for Alembic. Each test runs inside its own transaction that is
always rolled back, so nothing persists in `nexus` between test runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.core.types import DataClassification, ProviderName, TransformationType
from app.db.base import NEXUS_SCHEMA
from app.domain.provenance import ProvenanceCreate
from app.providers.base.http_client import ThrottledHttpClient


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    settings = get_settings()
    if not settings.database_url:
        pytest.skip("DATABASE_URL not configured; skipping integration tests")
    engine = create_engine(
        settings.database_url,
        connect_args={"options": f"-c search_path={NEXUS_SCHEMA},public"},
    )
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, autoflush=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        # A failed flush() (e.g. a CHECK constraint violation) triggers
        # SQLAlchemy's own implicit rollback, which also ends this outer,
        # externally-begun transaction — rolling back an already-inactive
        # Transaction emits a SAWarning, so only do it if still needed.
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def sec_http_client() -> Iterator[ThrottledHttpClient]:
    """A real HTTP client for live SEC EDGAR calls, skipped gracefully if
    SEC_USER_AGENT isn't configured — same gating pattern as `db_engine`."""
    settings = get_settings()
    if not settings.sec_user_agent:
        pytest.skip("SEC_USER_AGENT not configured; skipping live SEC EDGAR test")
    client = ThrottledHttpClient(user_agent=settings.sec_user_agent)
    try:
        yield client
    finally:
        client.close()


def reported_public_provenance(**overrides: object) -> ProvenanceCreate:
    """A minimal valid `ProvenanceCreate` for tests that just need *some* row.

    Shared across integration test modules rather than duplicated per file.
    """
    defaults: dict[str, object] = dict(
        provider=ProviderName.SEC_EDGAR,
        source_record_id="0000320193-24-000123",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019324000123",
        as_of_date=date.today(),
        retrieved_at=datetime.now(UTC),
        transformation=TransformationType.REPORTED,
        classification=DataClassification.PUBLIC,
    )
    defaults.update(overrides)
    return ProvenanceCreate(**defaults)  # type: ignore[arg-type]
