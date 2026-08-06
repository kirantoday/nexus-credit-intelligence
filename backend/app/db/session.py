"""Database session management.

Per PLAN.md section 3 (Domain layer), only repository modules are permitted to
import `get_db`/`SessionLocal` and open a session — providers and API routes
never touch SQLAlchemy directly. This module exists so `/health` can stay a
zero-dependency liveness check while the rest of the app is already wired for a
real database.

Repository functions (`app/repositories/**`) `flush()` but never `commit()` —
`get_db()` owns the transaction boundary: commit once, at the end of a
successful request, or roll back on any exception. This lets a single request
call several repository functions as one atomic unit of work.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.base import NEXUS_SCHEMA

_settings = get_settings()

_engine = (
    create_engine(
        _settings.database_url,
        pool_pre_ping=True,
        connect_args={
            # Belt-and-suspenders alongside Base.metadata's schema="nexus": every
            # connection resolves unqualified names to the nexus schema first, so a
            # query can never silently fall through to the other application's
            # tables in public.
            "options": f"-c search_path={NEXUS_SCHEMA},public",
            # Supabase's connection string points at its pgbouncer pooler in
            # transaction-pooling mode, which hands each query to a different
            # physical backend connection. psycopg3 normally caches server-side
            # PREPARE statements per logical connection; under transaction
            # pooling that cache goes stale (a later query can hit a backend
            # that never saw the PREPARE, or one where a stale prepared-statement
            # name collides with another client's), surfacing as intermittent
            # `InvalidSqlStatementName` / `DuplicatePreparedStatement` errors.
            # Disabling server-side prepare avoids the mismatch entirely.
            "prepare_threshold": None,
        },
    )
    if _settings.database_url
    else None
)
SessionLocal = (
    sessionmaker(bind=_engine, autocommit=False, autoflush=False) if _engine is not None else None
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session.

    Raises a clear error if DATABASE_URL isn't configured, rather than a
    confusing None-related AttributeError deep in SQLAlchemy.
    """
    if SessionLocal is None:
        raise RuntimeError(
            "DATABASE_URL is not configured. Set it in backend/.env (copied from "
            "the repository's .env.example) before using the database."
        )
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
