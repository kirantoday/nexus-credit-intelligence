"""Canonical domain object for the durable raw-response store (PLAN.md section 4.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.types import ProviderName


class RawProviderPayloadCreate(BaseModel):
    """Everything needed to create a `raw_provider_payload` row; id is server-generated."""

    model_config = ConfigDict(frozen=True)

    provider: ProviderName
    source_record_id: str
    request_fingerprint: str
    payload_json: dict[str, Any] | list[Any] | None = None
    storage_object_path: str | None = None
    retrieved_at: datetime
    checksum: str
    content_type: str
    size_bytes: int | None = None
    provenance_id: UUID | None = None

    @model_validator(mode="after")
    def _has_a_storage_location(self) -> RawProviderPayloadCreate:
        if self.payload_json is None and self.storage_object_path is None:
            raise ValueError("either payload_json or storage_object_path must be set")
        return self


class RawProviderPayload(RawProviderPayloadCreate):
    """A persisted `raw_provider_payload` row."""

    id: UUID
