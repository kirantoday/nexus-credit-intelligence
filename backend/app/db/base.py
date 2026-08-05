"""SQLAlchemy 2 declarative base.

Canonical domain tables (provenance, issuer, security, ...) are added to
`app/models/` starting in Milestone 2 and imported here (or in alembic/env.py)
so Alembic's autogenerate can see them. Milestone 1 intentionally has no models
yet — this module exists so the DB session and Alembic wiring are provable now.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
