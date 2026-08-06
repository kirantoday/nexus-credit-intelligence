"""SQLAlchemy 2 declarative base.

Canonical domain tables (provenance, issuer, security, ...) are added to
`app/models/` starting in Milestone 2 and imported here (or in alembic/env.py)
so Alembic's autogenerate can see them. Milestone 1 intentionally has no models
yet — this module exists so the DB session and Alembic wiring are provable now.

This Supabase project is shared with another application. Nexus is isolated to
the `nexus` Postgres schema: every table declared against `Base` defaults to
that schema, so a model can never accidentally land in `public` or collide with
the other application's tables.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NEXUS_SCHEMA = "nexus"


class Base(DeclarativeBase):
    metadata = MetaData(schema=NEXUS_SCHEMA)
