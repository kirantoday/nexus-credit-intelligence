"""Repository for `collection` / `collection_membership` (PLAN.md section 24.1).

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.types import (
    CollectionPriority,
    CollectionScope,
    CollectionType,
    CollectionVisibility,
    CurationMethod,
    VerificationStatus,
)
from app.domain.collection import (
    Collection,
    CollectionCreate,
    CollectionMembership,
    CollectionMembershipCreate,
)
from app.domain.issuer import Issuer
from app.models.collection import Collection as CollectionModel
from app.models.collection import CollectionMembership as CollectionMembershipModel
from app.models.issuer import Issuer as IssuerModel


def _collection_to_domain(row: CollectionModel) -> Collection:
    return Collection(
        id=row.id,
        slug=row.slug,
        name=row.name,
        description=row.description,
        collection_type=CollectionType(row.collection_type),
        scope=CollectionScope(row.scope),
        owner_user_id=row.owner_user_id,
        visibility=CollectionVisibility(row.visibility),
        curation_method=CurationMethod(row.curation_method),
        verification_status=VerificationStatus(row.verification_status),
        last_verified_at=row.last_verified_at,
        priority=CollectionPriority(row.priority) if row.priority else None,
        verification_count=row.verification_count,
        last_refresh_source=row.last_refresh_source,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _membership_to_domain(row: CollectionMembershipModel) -> CollectionMembership:
    return CollectionMembership(
        id=row.id,
        collection_id=row.collection_id,
        issuer_id=row.issuer_id,
        rationale=row.rationale,
        rationale_as_of_date=row.rationale_as_of_date,
        verification_status=VerificationStatus(row.verification_status),
        supporting_provenance_ids=(
            [UUID(pid) for pid in row.supporting_provenance_ids]
            if row.supporting_provenance_ids
            else None
        ),
        added_at=row.added_at,
        added_by=row.added_by,
        system_seeded=row.system_seeded,
    )


def create_collection(db: Session, data: CollectionCreate) -> Collection:
    row = CollectionModel(
        slug=data.slug,
        name=data.name,
        description=data.description,
        collection_type=data.collection_type.value,
        scope=data.scope.value,
        owner_user_id=data.owner_user_id,
        visibility=data.visibility.value,
        curation_method=data.curation_method.value,
        verification_status=data.verification_status.value,
        last_verified_at=data.last_verified_at,
        priority=data.priority.value if data.priority else None,
        verification_count=data.verification_count,
        last_refresh_source=data.last_refresh_source,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _collection_to_domain(row)


def get_collection(db: Session, collection_id: UUID) -> Collection | None:
    row = db.get(CollectionModel, collection_id)
    return _collection_to_domain(row) if row is not None else None


def get_collection_by_slug(db: Session, slug: str) -> Collection | None:
    stmt = select(CollectionModel).where(CollectionModel.slug == slug)
    row = db.execute(stmt).scalars().first()
    return _collection_to_domain(row) if row is not None else None


def update_curation_method(
    db: Session, collection_id: UUID, curation_method: CurationMethod
) -> Collection:
    """Narrow, single-purpose update (mirrors `filing_monitor_run_repository
    .complete_run`'s pattern) — lets an idempotent seed script self-heal a
    collection's `curation_method` in place on a re-run, rather than only
    ever setting it once at creation time. Added for Milestone 7.5: the
    15 Milestone 6.5 Research Universes were originally seeded with
    `curation_method=system_seeded`, which meant "populated by a script"
    at the time but is corrected here to `manual_curated` — each candidate
    was in fact a human-selected, individually-rationale'd company, which
    is what genuinely distinguishes it from Milestone 7.5's new evidence-
    driven universes (which populate membership with no human candidate
    list at all).
    """
    row = db.get(CollectionModel, collection_id)
    if row is None:
        raise ValueError(f"collection {collection_id} not found")
    row.curation_method = curation_method.value
    db.flush()
    db.refresh(row)
    return _collection_to_domain(row)


def list_collections(
    db: Session, *, collection_type: CollectionType | None = None
) -> list[Collection]:
    stmt = select(CollectionModel).order_by(CollectionModel.name.asc())
    if collection_type is not None:
        stmt = stmt.where(CollectionModel.collection_type == collection_type.value)
    rows = db.execute(stmt).scalars().all()
    return [_collection_to_domain(row) for row in rows]


def remove_membership(db: Session, collection_id: UUID, issuer_id: UUID) -> bool:
    """Removes a curated membership decision. Unlike `provenance`/`calculation`
    (immutable audit-trail facts, ADR-014), a `collection_membership` row is
    a curation *decision*, not a fact about the world — a wrong or
    superseded curation call is legitimately correctable. Returns whether a
    row was actually removed (idempotent: `False`, not an error, if it
    didn't exist).
    """
    stmt = select(CollectionMembershipModel).where(
        CollectionMembershipModel.collection_id == collection_id,
        CollectionMembershipModel.issuer_id == issuer_id,
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


def add_membership(
    db: Session, data: CollectionMembershipCreate
) -> tuple[CollectionMembership, bool]:
    """Idempotent membership add. Returns (membership, created) — `created`
    is False when `(collection_id, issuer_id)` already existed, so callers
    (the seed script especially) can safely re-run without duplicating rows
    or raising on a unique-constraint violation.
    """
    existing_stmt = select(CollectionMembershipModel).where(
        CollectionMembershipModel.collection_id == data.collection_id,
        CollectionMembershipModel.issuer_id == data.issuer_id,
    )
    existing = db.execute(existing_stmt).scalars().first()
    if existing is not None:
        return _membership_to_domain(existing), False

    row = CollectionMembershipModel(
        collection_id=data.collection_id,
        issuer_id=data.issuer_id,
        rationale=data.rationale,
        rationale_as_of_date=data.rationale_as_of_date,
        verification_status=data.verification_status.value,
        supporting_provenance_ids=(
            [str(pid) for pid in data.supporting_provenance_ids]
            if data.supporting_provenance_ids
            else None
        ),
        added_by=data.added_by,
        system_seeded=data.system_seeded,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _membership_to_domain(row), True


def upgrade_membership_verification(
    db: Session,
    collection_id: UUID,
    issuer_id: UUID,
    *,
    verification_status: VerificationStatus,
    rationale: str,
    rationale_as_of_date: date | None,
    supporting_provenance_ids: list[UUID] | None,
) -> CollectionMembership | None:
    """Upgrades an existing membership's `verification_status` (e.g.
    `partial` -> `verified`) when stronger evidence arrives later — never
    downgrades (PLAN.md Milestone 7.5: system-suggested classifications
    become automatic ones as evidence strengthens, never the reverse).
    Returns `None` if no membership exists yet (the caller should
    `add_membership` first in that case)."""
    stmt = select(CollectionMembershipModel).where(
        CollectionMembershipModel.collection_id == collection_id,
        CollectionMembershipModel.issuer_id == issuer_id,
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        return None

    rank = {"unverified": 0, "partial": 1, "verified": 2}
    if rank[verification_status.value] <= rank[row.verification_status]:
        return _membership_to_domain(row)

    row.verification_status = verification_status.value
    row.rationale = rationale
    row.rationale_as_of_date = rationale_as_of_date
    if supporting_provenance_ids:
        row.supporting_provenance_ids = [str(pid) for pid in supporting_provenance_ids]
    db.flush()
    db.refresh(row)
    return _membership_to_domain(row)


def set_membership_verification(
    db: Session,
    collection_id: UUID,
    issuer_id: UUID,
    *,
    verification_status: VerificationStatus,
    rationale: str,
    rationale_as_of_date: date | None,
    supporting_provenance_ids: list[UUID] | None,
) -> CollectionMembership | None:
    """Sets an existing membership's `verification_status` unconditionally —
    including a *downgrade* (`verified` -> `partial`), which
    `upgrade_membership_verification` deliberately never does. Reserved for
    `app.scripts.reclassify_system_universes`'s controlled, auditable
    correction pass (PLAN.md Milestone 7.5.1 section 9): the live,
    incremental classification path (`universe_classification_service
    .classify_issuer`) must stay upgrade-only, but a bug that caused a
    membership to be wrongly `verified` in the first place cannot be
    corrected by a mechanism that can only ever move status upward.
    Returns `None` if no membership exists yet."""
    stmt = select(CollectionMembershipModel).where(
        CollectionMembershipModel.collection_id == collection_id,
        CollectionMembershipModel.issuer_id == issuer_id,
    )
    row = db.execute(stmt).scalars().first()
    if row is None:
        return None

    row.verification_status = verification_status.value
    row.rationale = rationale
    row.rationale_as_of_date = rationale_as_of_date
    if supporting_provenance_ids:
        row.supporting_provenance_ids = [str(pid) for pid in supporting_provenance_ids]
    db.flush()
    db.refresh(row)
    return _membership_to_domain(row)


def list_memberships_by_collection(db: Session, collection_id: UUID) -> list[CollectionMembership]:
    stmt = select(CollectionMembershipModel).where(
        CollectionMembershipModel.collection_id == collection_id
    )
    rows = db.execute(stmt).scalars().all()
    return [_membership_to_domain(row) for row in rows]


def get_membership(
    db: Session, collection_id: UUID, issuer_id: UUID
) -> CollectionMembership | None:
    """The single membership row for one (collection, issuer) pair — used
    when the caller already knows both ids (e.g. rendering an issuer's own
    membership rationale for each collection it belongs to) rather than
    fetching every membership in the collection just to filter one out."""
    stmt = select(CollectionMembershipModel).where(
        CollectionMembershipModel.collection_id == collection_id,
        CollectionMembershipModel.issuer_id == issuer_id,
    )
    row = db.execute(stmt).scalars().first()
    return _membership_to_domain(row) if row is not None else None


def list_collections_for_issuer(db: Session, issuer_id: UUID) -> list[Collection]:
    """Every Research Universe / Watchlist / Benchmark an issuer belongs to —
    backs Issuer Detail's membership section (PLAN.md 24.9)."""
    stmt = (
        select(CollectionModel)
        .join(
            CollectionMembershipModel,
            CollectionMembershipModel.collection_id == CollectionModel.id,
        )
        .where(CollectionMembershipModel.issuer_id == issuer_id)
        .order_by(CollectionModel.name.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_collection_to_domain(row) for row in rows]


def count_members(db: Session, collection_id: UUID) -> int:
    stmt = select(func.count()).where(CollectionMembershipModel.collection_id == collection_id)
    return db.execute(stmt).scalar_one()


def list_issuer_ids_for_collection_types(
    db: Session, collection_types: list[CollectionType]
) -> list[UUID]:
    """Distinct issuers covered by any collection of the given types — the
    overnight monitor's target population (PLAN.md 24.5): every issuer under
    a `research_universe` or `benchmark` collection, not `watchlist` (personal/
    team, Milestone 8, out of scope for the monitor)."""
    stmt = (
        select(CollectionMembershipModel.issuer_id)
        .join(CollectionModel, CollectionModel.id == CollectionMembershipModel.collection_id)
        .where(CollectionModel.collection_type.in_([t.value for t in collection_types]))
        .distinct()
    )
    return list(db.execute(stmt).scalars().all())


def _issuer_row_to_domain(row: IssuerModel) -> Issuer:
    """Mirrors `issuer_repository._to_domain` — duplicated rather than
    imported across repository modules (each repository owns its own
    ORM<->domain mapping, per this codebase's established convention)."""
    return Issuer(
        id=row.id,
        legal_name=row.legal_name,
        cik=row.cik,
        lei=row.lei,
        ticker=row.ticker,
        sic=row.sic,
        sector=row.sector,
        is_synthetic=row.is_synthetic,
        synthetic_reason=row.synthetic_reason,
        provenance_id=row.provenance_id,
    )


def list_issuers_for_collection(
    db: Session, collection_id: UUID
) -> list[tuple[Issuer, CollectionMembership]]:
    """Issuer domain objects + their membership record for one collection —
    backs `GET /api/research-universes/{id}/issuers`."""
    stmt = (
        select(IssuerModel, CollectionMembershipModel)
        .join(
            CollectionMembershipModel,
            CollectionMembershipModel.issuer_id == IssuerModel.id,
        )
        .where(CollectionMembershipModel.collection_id == collection_id)
        .order_by(IssuerModel.legal_name.asc())
    )
    rows = db.execute(stmt).all()
    return [
        (_issuer_row_to_domain(issuer_row), _membership_to_domain(membership_row))
        for issuer_row, membership_row in rows
    ]
