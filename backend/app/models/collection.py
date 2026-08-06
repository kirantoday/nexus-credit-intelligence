"""ORM models for `collection` and `collection_membership` (PLAN.md section 24.1).

Research Universes and Watchlists are distinct, coexisting product concepts
that share these two generalized tables rather than a dedicated `watchlist`
table (ADR-016) — distinguished by `collection_type`. Membership is a curated
coverage decision, never a current-status assertion: it carries `rationale` +
`rationale_as_of_date`, not a status flag.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import (
    CollectionPriority,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    VerificationStatus,
)
from app.db.base import Base

_COLLECTION_TYPE_SQL_LIST = ", ".join(f"'{value}'" for value in CollectionType)
_SCOPE_SQL_LIST = ", ".join(f"'{value}'" for value in CollectionScope)
_VISIBILITY_SQL_LIST = ", ".join(f"'{value}'" for value in CollectionVisibility)
_CURATION_METHOD_SQL_LIST = ", ".join(f"'{value}'" for value in CurationMethod)
_VERIFICATION_STATUS_SQL_LIST = ", ".join(f"'{value}'" for value in VerificationStatus)
_PRIORITY_SQL_LIST = ", ".join(f"'{value}'" for value in CollectionPriority)


class Collection(Base):
    __tablename__ = "collection"
    __table_args__ = (
        CheckConstraint(
            f"collection_type IN ({_COLLECTION_TYPE_SQL_LIST})",
            name="ck_collection_type",
        ),
        CheckConstraint(f"scope IN ({_SCOPE_SQL_LIST})", name="ck_collection_scope"),
        CheckConstraint(f"visibility IN ({_VISIBILITY_SQL_LIST})", name="ck_collection_visibility"),
        CheckConstraint(
            f"curation_method IN ({_CURATION_METHOD_SQL_LIST})",
            name="ck_collection_curation_method",
        ),
        CheckConstraint(
            f"verification_status IN ({_VERIFICATION_STATUS_SQL_LIST})",
            name="ck_collection_verification_status",
        ),
        CheckConstraint(
            f"priority IS NULL OR priority IN ({_PRIORITY_SQL_LIST})",
            name="ck_collection_priority",
        ),
        Index("ix_collection_slug", "slug", unique=True),
        Index("ix_collection_collection_type", "collection_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    collection_type: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'organization'"))
    owner_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'public'"))
    curation_method: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[str] = mapped_column(Text, nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_refresh_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CollectionMembership(Base):
    __tablename__ = "collection_membership"
    __table_args__ = (
        CheckConstraint(
            f"verification_status IN ({_VERIFICATION_STATUS_SQL_LIST})",
            name="ck_collection_membership_verification_status",
        ),
        UniqueConstraint("collection_id", "issuer_id", name="uq_collection_membership_pair"),
        Index("ix_collection_membership_collection_id", "collection_id"),
        Index("ix_collection_membership_issuer_id", "issuer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("collection.id"), nullable=False
    )
    issuer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("issuer.id"), nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    verification_status: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_provenance_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    added_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_seeded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
