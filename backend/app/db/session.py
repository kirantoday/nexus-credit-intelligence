"""Database session management.

Per PLAN.md section 3 (Domain layer), only repository modules are permitted to
import `get_db`/`SessionLocal` and open a session — providers and API routes
never touch SQLAlchemy directly. Milestone 1 has no repositories yet; this
module exists so later milestones have a single, already-tested place to get a
session from, and so `/health` can stay a zero-dependency liveness check while
the rest of the app is already wired for a real database.
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
        # Belt-and-suspenders alongside Base.metadata's schema="nexus": every
        # connection resolves unqualified names to the nexus schema first, so a
        # query can never silently fall through to the other application's
        # tables in public.
        connect_args={"options": f"-c search_path={NEXUS_SCHEMA},public"},
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
    finally:
        db.close()
