"""Canonical domain objects for `collection` / `collection_membership` (PLAN.md 24.1).

Research Universes and Watchlists are distinct, coexisting concepts sharing
this generalized table pair (ADR-016), distinguished by `collection_type`.
Membership is a curated coverage decision, never a current-status assertion:
`rationale` + `rationale_as_of_date` are dated text a human wrote/verified,
never a bare "is currently distressed" flag.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.types import (
    CollectionPriority,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    VerificationStatus,
)


class CollectionCreate(BaseModel):
    """Everything needed to create a `collection` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    slug: str
    name: str
    description: str
    collection_type: CollectionType
    scope: CollectionScope = CollectionScope.ORGANIZATION
    owner_user_id: str | None = None
    visibility: CollectionVisibility = CollectionVisibility.PUBLIC
    curation_method: CurationMethod
    verification_status: VerificationStatus
    last_verified_at: datetime | None = None
    priority: CollectionPriority | None = None
    verification_count: int = 0
    last_refresh_source: str | None = None


class Collection(CollectionCreate):
    """A persisted `collection` row."""

    id: UUID
    created_at: datetime
    updated_at: datetime


class CollectionMembershipCreate(BaseModel):
    """Everything needed to create a `collection_membership` row."""

    model_config = ConfigDict(frozen=True)

    collection_id: UUID
    issuer_id: UUID
    rationale: str
    rationale_as_of_date: date | None = None
    verification_status: VerificationStatus
    supporting_provenance_ids: list[UUID] | None = None
    added_by: str | None = None
    system_seeded: bool = True


class CollectionMembership(CollectionMembershipCreate):
    """A persisted `collection_membership` row."""

    id: UUID
    added_at: datetime
