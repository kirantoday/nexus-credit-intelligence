"""public_document_approval (DRAFT — not applied)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-23

Milestone 10D.2 (ADR-021): the server-controlled allowlist of documents
whose content may be sent to an external embedding vendor and, in 10D.3+,
returned by retrieval. Purely additive; touches no existing table.

Rows are written only by `app.scripts.approve_public_document`. A partial
unique index allows at most one *active* (unrevoked) approval per document.
`approved_raw_payload_checksum` pins the exact stored file; a derived
(converted) document must record its source hash and converter identity.

Nexus-owned objects only, all in the `nexus` schema. The `vector` and
`pg_trgm` extensions are not touched.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_document_approval",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("research_document_id", sa.UUID(), nullable=False),
        sa.Column("approved_raw_payload_checksum", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.Text(), nullable=True),
        sa.Column("converter_name", sa.Text(), nullable=True),
        sa.Column("converter_version", sa.Text(), nullable=True),
        sa.Column("page_reference_basis", sa.Text(), nullable=False),
        sa.Column("approval_basis", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Text(), nullable=False),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "page_reference_basis IN ('original', 'converted_pdf')",
            name="ck_public_document_approval_page_reference_basis",
        ),
        sa.CheckConstraint(
            "approved_raw_payload_checksum ~ '^[0-9a-f]{64}$'",
            name="ck_public_document_approval_checksum_format",
        ),
        sa.CheckConstraint(
            "source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_public_document_approval_source_sha256_format",
        ),
        sa.CheckConstraint(
            "page_reference_basis = 'original' OR "
            "(source_sha256 IS NOT NULL AND converter_name IS NOT NULL "
            "AND converter_version IS NOT NULL)",
            name="ck_public_document_approval_derived_requires_lineage",
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL) = (revoked_by IS NULL)",
            name="ck_public_document_approval_revocation_pair",
        ),
        sa.CheckConstraint("length(approval_basis) > 0", name="ck_public_document_approval_basis"),
        sa.ForeignKeyConstraint(["research_document_id"], ["nexus.research_document.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_public_document_approval_research_document_id",
        "public_document_approval",
        ["research_document_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ux_public_document_approval_one_active",
        "public_document_approval",
        ["research_document_id"],
        unique=True,
        schema="nexus",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_public_document_approval_one_active",
        table_name="public_document_approval",
        schema="nexus",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.drop_index(
        "ix_public_document_approval_research_document_id",
        table_name="public_document_approval",
        schema="nexus",
    )
    op.drop_table("public_document_approval", schema="nexus")
