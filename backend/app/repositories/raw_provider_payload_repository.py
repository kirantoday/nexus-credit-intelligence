"""Repository for `raw_provider_payload`, the durable raw-response store.

See `provenance_repository.py`'s module docstring for this project's
repository conventions (function-style, domain objects only, flush-not-commit).

`retrieved_at`/`checksum`/`payload_json`/`storage_object_path` are immutable
once written (PLAN.md section 4.4) — the only supported mutation is
`link_provenance`, setting the back-reference once a `provenance` row has been
created from this payload.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.types import ProviderName
from app.domain.raw_provider_payload import RawProviderPayload, RawProviderPayloadCreate
from app.models.raw_provider_payload import RawProviderPayload as RawProviderPayloadModel


def _to_domain(row: RawProviderPayloadModel) -> RawProviderPayload:
    return RawProviderPayload(
        id=row.id,
        provider=ProviderName(row.provider),
        source_record_id=row.source_record_id,
        request_fingerprint=row.request_fingerprint,
        payload_json=row.payload_json,
        storage_object_path=row.storage_object_path,
        retrieved_at=row.retrieved_at,
        checksum=row.checksum,
        content_type=row.content_type,
        provenance_id=row.provenance_id,
    )


def create_payload(db: Session, data: RawProviderPayloadCreate) -> RawProviderPayload:
    row = RawProviderPayloadModel(
        provider=data.provider.value,
        source_record_id=data.source_record_id,
        request_fingerprint=data.request_fingerprint,
        payload_json=data.payload_json,
        storage_object_path=data.storage_object_path,
        retrieved_at=data.retrieved_at,
        checksum=data.checksum,
        content_type=data.content_type,
        provenance_id=data.provenance_id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _to_domain(row)


def get_payload(db: Session, payload_id: UUID) -> RawProviderPayload | None:
    row = db.get(RawProviderPayloadModel, payload_id)
    return _to_domain(row) if row is not None else None


def get_by_request_fingerprint(
    db: Session, provider: str, request_fingerprint: str
) -> RawProviderPayload | None:
    """Idempotent re-fetch check (PLAN.md 4.4): has this exact request already been made."""
    stmt = select(RawProviderPayloadModel).where(
        RawProviderPayloadModel.provider == provider,
        RawProviderPayloadModel.request_fingerprint == request_fingerprint,
    )
    row = db.execute(stmt).scalars().first()
    return _to_domain(row) if row is not None else None


def link_provenance(db: Session, payload_id: UUID, provenance_id: UUID) -> RawProviderPayload:
    row = db.get(RawProviderPayloadModel, payload_id)
    if row is None:
        raise ValueError(f"raw_provider_payload {payload_id} not found")
    row.provenance_id = provenance_id
    db.flush()
    db.refresh(row)
    return _to_domain(row)
