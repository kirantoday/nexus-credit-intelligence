"""document_extraction and document_chunk

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-13 12:12:42.709093

Milestone 10C (Document Intelligence): the canonical extraction/chunking
layer — `research_document -> document_extraction -> document_chunk`.
`document_extraction` is one immutable attempt per reprocessing; a partial
unique index (`ux_document_extraction_one_current_per_document`, scoped to
`WHERE is_current`) enforces "at most one current extraction per source
document" at the database level, not just in application code. A
CHECK constraint (`ck_document_extraction_current_requires_completed`)
additionally guarantees a `processing`/`failed`/`needs_ocr` row can never
be promoted current.

`document_chunk.issuer_id`/`confidentiality_classification` are
deliberate denormalizations off `document_extraction`/`research_document`
(see `app.models.document_chunk`'s module docstring) — filtering
performance plus a guardrail property: access classification is always
directly present on the row a future retrieval query reads. `search_vector`
mirrors Migration 0016/0018's exact generated-tsvector-column pattern,
backing 10C's internal `search_document_chunks` capability only — this
migration adds nothing to Universal Search's entity-type list.

Purely additive: no existing table/column is touched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_extraction",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "source_type",
            sa.Text(),
            server_default=sa.text("'research_document'"),
            nullable=False,
        ),
        sa.Column("research_document_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("extractor_provider", sa.Text(), nullable=True),
        sa.Column("extractor_version", sa.Text(), nullable=True),
        sa.Column("chunking_strategy_version", sa.Text(), nullable=True),
        sa.Column("structured_artifact_storage_key", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("table_count", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_classification", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "(NOT is_current) OR (status = 'completed')",
            name="ck_document_extraction_current_requires_completed",
        ),
        sa.CheckConstraint(
            "error_classification IS NULL OR error_classification IN "
            "('transient', 'deterministic')",
            name="ck_document_extraction_error_classification",
        ),
        sa.CheckConstraint(
            "source_type != 'research_document' OR research_document_id IS NOT NULL",
            name="ck_document_extraction_research_document_source_requires_fk",
        ),
        sa.CheckConstraint(
            "source_type IN ('research_document')", name="ck_document_extraction_source_type"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'needs_ocr')",
            name="ck_document_extraction_status",
        ),
        sa.ForeignKeyConstraint(["research_document_id"], ["nexus.research_document.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_document_extraction_research_document_id",
        "document_extraction",
        ["research_document_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_document_extraction_status",
        "document_extraction",
        ["status"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ux_document_extraction_one_current_per_document",
        "document_extraction",
        ["research_document_id"],
        unique=True,
        schema="nexus",
        postgresql_where=sa.text("is_current"),
    )
    op.create_table(
        "document_chunk",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_extraction_id", sa.UUID(), nullable=False),
        sa.Column("research_document_id", sa.UUID(), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("element_type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), server_default=sa.text("'markdown'"), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.Text(), nullable=True),
        sa.Column("section_title", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("confidentiality_classification", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "confidentiality_classification IN ('standard', 'restricted')",
            name="ck_document_chunk_confidentiality_classification",
        ),
        sa.CheckConstraint(
            "element_type IN ('text', 'heading', 'table', 'list')",
            name="ck_document_chunk_element_type",
        ),
        sa.CheckConstraint(
            "page_start IS NULL OR page_end IS NULL OR page_start <= page_end",
            name="ck_document_chunk_page_range_valid",
        ),
        sa.ForeignKeyConstraint(["document_extraction_id"], ["nexus.document_extraction.id"]),
        sa.ForeignKeyConstraint(["issuer_id"], ["nexus.issuer.id"]),
        sa.ForeignKeyConstraint(["research_document_id"], ["nexus.research_document.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_extraction_id", "chunk_index", name="ux_document_chunk_extraction_ordinal"
        ),
        schema="nexus",
    )
    op.create_index(
        "ix_document_chunk_document_extraction_id",
        "document_chunk",
        ["document_extraction_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_document_chunk_issuer_id",
        "document_chunk",
        ["issuer_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_document_chunk_research_document_id",
        "document_chunk",
        ["research_document_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_document_chunk_search_vector",
        "document_chunk",
        ["search_vector"],
        unique=False,
        schema="nexus",
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_chunk_search_vector",
        table_name="document_chunk",
        schema="nexus",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_document_chunk_research_document_id", table_name="document_chunk", schema="nexus"
    )
    op.drop_index("ix_document_chunk_issuer_id", table_name="document_chunk", schema="nexus")
    op.drop_index(
        "ix_document_chunk_document_extraction_id", table_name="document_chunk", schema="nexus"
    )
    op.drop_table("document_chunk", schema="nexus")
    op.drop_index(
        "ux_document_extraction_one_current_per_document",
        table_name="document_extraction",
        schema="nexus",
        postgresql_where=sa.text("is_current"),
    )
    op.drop_index("ix_document_extraction_status", table_name="document_extraction", schema="nexus")
    op.drop_index(
        "ix_document_extraction_research_document_id",
        table_name="document_extraction",
        schema="nexus",
    )
    op.drop_table("document_extraction", schema="nexus")
