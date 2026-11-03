"""Canonical domain objects for `public_document_approval` (Milestone
10D.2). See `app.models.public_document_approval` for the allowlist
semantics; validators here mirror the table's CHECK constraints so a bad
approval is rejected before it reaches the database."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.types import PageReferenceBasis

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PublicDocumentApprovalCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    research_document_id: uuid.UUID
    approved_raw_payload_checksum: str
    source_url: str
    source_sha256: str | None = None
    converter_name: str | None = None
    converter_version: str | None = None
    page_reference_basis: PageReferenceBasis
    approval_basis: str
    approved_by: str

    @field_validator("approved_raw_payload_checksum")
    @classmethod
    def _checksum_is_sha256(cls, value: str) -> str:
        if not _SHA256_RE.match(value):
            raise ValueError("approved_raw_payload_checksum must be a lowercase hex SHA-256")
        return value

    @field_validator("source_sha256")
    @classmethod
    def _source_sha_is_sha256(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256_RE.match(value):
            raise ValueError("source_sha256 must be a lowercase hex SHA-256")
        return value

    @field_validator("approval_basis", "approved_by", "source_url")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _derived_documents_record_lineage(self) -> PublicDocumentApprovalCreate:
        if self.page_reference_basis is PageReferenceBasis.CONVERTED_PDF and (
            self.source_sha256 is None or not self.converter_name or not self.converter_version
        ):
            raise ValueError(
                "a converted_pdf approval must record source_sha256, converter_name, and "
                "converter_version"
            )
        return self


class PublicDocumentApproval(PublicDocumentApprovalCreate):
    """A persisted `public_document_approval` row."""

    id: uuid.UUID
    approved_at: datetime
    revoked_at: datetime | None
    revoked_by: str | None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
