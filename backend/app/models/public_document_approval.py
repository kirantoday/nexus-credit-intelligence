"""ORM model for `public_document_approval` (Milestone 10D.2, ADR-021) —
the server-controlled allowlist of documents whose content may be sent to
an external embedding vendor and, in 10D.3+, returned by retrieval.

Rows are created only by `app.scripts.approve_public_document` (an operator
tool). There is deliberately no API route and no domain path that lets a
request create or widen an approval. A client-supplied
`research_document.confidentiality_classification = 'standard'` is
necessary for eligibility but never sufficient — see
`app.retrieval.eligibility`.

`approved_raw_payload_checksum` pins the exact stored file (SHA-256) the
approval was granted for; a document whose stored payload no longer matches
is ineligible. For a document derived from another source (for example an
SEC HTML exhibit converted to PDF), the original's URL and hash and the
converter identity are recorded here, and `page_reference_basis =
'converted_pdf'` makes citations label pages as converted-PDF pages rather
than the original source's pages.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import PageReferenceBasis
from app.db.base import Base

_BASIS_SQL_LIST = ", ".join(f"'{value}'" for value in PageReferenceBasis)
_SHA256_RE = "^[0-9a-f]{64}$"


class PublicDocumentApproval(Base):
    __tablename__ = "public_document_approval"
    __table_args__ = (
        CheckConstraint(
            f"page_reference_basis IN ({_BASIS_SQL_LIST})",
            name="ck_public_document_approval_page_reference_basis",
        ),
        CheckConstraint(
            f"approved_raw_payload_checksum ~ '{_SHA256_RE}'",
            name="ck_public_document_approval_checksum_format",
        ),
        CheckConstraint(
            f"source_sha256 IS NULL OR source_sha256 ~ '{_SHA256_RE}'",
            name="ck_public_document_approval_source_sha256_format",
        ),
        # A converted/derived document must record what it was derived
        # from and how, so the transformation is auditable.
        CheckConstraint(
            "page_reference_basis = 'original' OR "
            "(source_sha256 IS NOT NULL AND converter_name IS NOT NULL "
            "AND converter_version IS NOT NULL)",
            name="ck_public_document_approval_derived_requires_lineage",
        ),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_by IS NULL)",
            name="ck_public_document_approval_revocation_pair",
        ),
        CheckConstraint("length(approval_basis) > 0", name="ck_public_document_approval_basis"),
        Index("ix_public_document_approval_research_document_id", "research_document_id"),
        # At most one *active* approval per document, enforced by Postgres.
        Index(
            "ux_public_document_approval_one_active",
            "research_document_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    research_document_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_document.id"), nullable=False
    )
    approved_raw_payload_checksum: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    converter_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    converter_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_reference_basis: Mapped[str] = mapped_column(Text, nullable=False)
    approval_basis: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(Text, nullable=True)
