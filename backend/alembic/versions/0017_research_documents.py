"""research documents

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-12 22:00:00.000000

Milestone 10B (PLAN.md 4.10, row 9 slice): `research_document` — general
analyst research material (credit agreements, presentations, internal
memos) associated with an issuer, distinct from `docket_document` (court
filings). Also adds `raw_provider_payload.size_bytes` (nullable bigint), a
generic byte-size column for every large payload that table stores
(admin-uploaded research documents today; filings/court documents/TRACE
extracts whenever those start recording it too).

No search_vector column here — Universal Search integration (title/metadata
only, no extracted content) is a separately-approved follow-up migration
(10B-5), matching how Milestone 12A added search_vector to seven
already-existing tables in its own dedicated migration.

`extracted_text` is a reserved, nullable slot per PLAN.md 4.10 — never
populated by this milestone (no PDF extraction in 10B).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "raw_provider_payload",
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        schema="nexus",
    )

    op.create_table(
        "research_document",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("security_id", sa.UUID(), nullable=True),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("raw_payload_id", sa.UUID(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("document_date", sa.Date(), nullable=True),
        sa.Column(
            "confidentiality_classification",
            sa.Text(),
            server_default=sa.text("'standard'"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.Text(), nullable=True),
        sa.Column("provenance_id", sa.UUID(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "document_type IN ('credit_agreement', 'amendment', 'earnings_presentation', "
            "'investor_presentation', 'restructuring_presentation', 'lender_presentation', "
            "'bankruptcy_court_document', 'financial_model_analysis', "
            "'internal_research_memo', 'other')",
            name="ck_research_document_document_type",
        ),
        sa.CheckConstraint(
            "confidentiality_classification IN ('standard', 'restricted')",
            name="ck_research_document_confidentiality_classification",
        ),
        sa.CheckConstraint(
            "(is_archived AND archived_at IS NOT NULL) OR (NOT is_archived AND archived_at IS NULL)",
            name="ck_research_document_archived_requires_timestamp",
        ),
        sa.ForeignKeyConstraint(["issuer_id"], ["nexus.issuer.id"]),
        sa.ForeignKeyConstraint(["security_id"], ["nexus.security.id"]),
        sa.ForeignKeyConstraint(["raw_payload_id"], ["nexus.raw_provider_payload.id"]),
        sa.ForeignKeyConstraint(["provenance_id"], ["nexus.provenance.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_research_document_issuer_id",
        "research_document",
        ["issuer_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_research_document_security_id",
        "research_document",
        ["security_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_research_document_is_archived",
        "research_document",
        ["is_archived"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_research_document_raw_payload_id",
        "research_document",
        ["raw_payload_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_research_document_provenance_id",
        "research_document",
        ["provenance_id"],
        unique=False,
        schema="nexus",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_document_provenance_id", table_name="research_document", schema="nexus"
    )
    op.drop_index(
        "ix_research_document_raw_payload_id", table_name="research_document", schema="nexus"
    )
    op.drop_index(
        "ix_research_document_is_archived", table_name="research_document", schema="nexus"
    )
    op.drop_index(
        "ix_research_document_security_id", table_name="research_document", schema="nexus"
    )
    op.drop_index("ix_research_document_issuer_id", table_name="research_document", schema="nexus")
    op.drop_table("research_document", schema="nexus")
    op.drop_column("raw_provider_payload", "size_bytes", schema="nexus")
