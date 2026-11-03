"""document_embedding_job, document_chunk_embedding, embedding_call_log (DRAFT — not applied)

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-23

**DRAFT — do not move into `alembic/versions/` until the embedding provider
and model are approved.** The only unsettled element is the fixed vector
width below (`EMBEDDING_DIMENSION`). It is hard-coded here rather than read
from application code on purpose (a migration must not change meaning when
application constants change); a unit test fails if it ever disagrees with
`app.embeddings.dimensions.EMBEDDING_COLUMN_DIMENSION`.

A fixed-width pgvector column cannot be changed in place: a different width
means a new column or table and re-embedding. 1024 is a pilot value chosen
only because both leading candidate vendors produce it natively (ADR-021).

Purely additive; touches no existing table. `document_embedding_job`
enforces at most one *active* job per (extraction, model, version) with a
partial unique index, so finished jobs remain as history and a re-embedding
can be enqueued later. `document_chunk_embedding` is unique per (chunk,
model, model version) and carries `CHECK (vector_dims(embedding) =
dimension)`. No ANN (HNSW/IVFFlat) index: exact cosine scans first.

The `vector` extension already exists (migration 0001) and is never created,
altered, or dropped here, including on downgrade. Downgrade drops only the
three Nexus tables created below.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSION = 1024  # DRAFT pilot width — confirm against the approved model.


class _Vector(sa.types.UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: object) -> str:
        return f"vector({self.dimensions})"


def upgrade() -> None:
    op.create_table(
        "document_embedding_job",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("research_document_id", sa.UUID(), nullable=False),
        sa.Column("document_extraction_id", sa.UUID(), nullable=False),
        sa.Column("embedding_provider", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("embedding_model_version", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_classification", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("chunk_total", sa.Integer(), nullable=True),
        sa.Column("chunks_embedded", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("chunks_replaced", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("provenance_id", sa.UUID(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'blocked_ineligible')",
            name="ck_document_embedding_job_status",
        ),
        sa.CheckConstraint(
            "error_classification IS NULL OR "
            "error_classification IN ('transient', 'deterministic')",
            name="ck_document_embedding_job_error_classification",
        ),
        sa.CheckConstraint("dimension > 0", name="ck_document_embedding_job_dimension"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_document_embedding_job_attempt_count"),
        sa.ForeignKeyConstraint(["research_document_id"], ["nexus.research_document.id"]),
        sa.ForeignKeyConstraint(["document_extraction_id"], ["nexus.document_extraction.id"]),
        sa.ForeignKeyConstraint(["provenance_id"], ["nexus.provenance.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_document_embedding_job_status",
        "document_embedding_job",
        ["status"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_document_embedding_job_document_extraction_id",
        "document_embedding_job",
        ["document_extraction_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_document_embedding_job_research_document_id",
        "document_embedding_job",
        ["research_document_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ux_document_embedding_job_one_active_per_target",
        "document_embedding_job",
        ["document_extraction_id", "embedding_model", "embedding_model_version"],
        unique=True,
        schema="nexus",
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )

    op.create_table(
        "document_chunk_embedding",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("chunk_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("embedding_model_version", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("content_fingerprint", sa.Text(), nullable=False),
        sa.Column("embedding", _Vector(EMBEDDING_DIMENSION), nullable=False),
        sa.Column("provenance_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_document_chunk_embedding_fingerprint_format",
        ),
        sa.CheckConstraint(
            "vector_dims(embedding) = dimension", name="ck_document_chunk_embedding_dim"
        ),
        sa.CheckConstraint("revision >= 1", name="ck_document_chunk_embedding_revision"),
        sa.ForeignKeyConstraint(["chunk_id"], ["nexus.document_chunk.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["nexus.document_embedding_job.id"]),
        sa.ForeignKeyConstraint(["provenance_id"], ["nexus.provenance.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ux_document_chunk_embedding_chunk_model",
        "document_chunk_embedding",
        ["chunk_id", "embedding_model", "embedding_model_version"],
        unique=True,
        schema="nexus",
    )
    op.create_index(
        "ix_document_chunk_embedding_job_id",
        "document_chunk_embedding",
        ["job_id"],
        unique=False,
        schema="nexus",
    )

    op.create_table(
        "embedding_call_log",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_classification", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('document', 'query')", name="ck_embedding_call_log_purpose"
        ),
        sa.CheckConstraint("batch_size > 0", name="ck_embedding_call_log_batch_size"),
        sa.ForeignKeyConstraint(["job_id"], ["nexus.document_embedding_job.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_embedding_call_log_job_id",
        "embedding_call_log",
        ["job_id"],
        unique=False,
        schema="nexus",
    )


def downgrade() -> None:
    op.drop_index("ix_embedding_call_log_job_id", table_name="embedding_call_log", schema="nexus")
    op.drop_table("embedding_call_log", schema="nexus")

    op.drop_index(
        "ix_document_chunk_embedding_job_id", table_name="document_chunk_embedding", schema="nexus"
    )
    op.drop_index(
        "ux_document_chunk_embedding_chunk_model",
        table_name="document_chunk_embedding",
        schema="nexus",
    )
    op.drop_table("document_chunk_embedding", schema="nexus")

    op.drop_index(
        "ux_document_embedding_job_one_active_per_target",
        table_name="document_embedding_job",
        schema="nexus",
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )
    op.drop_index(
        "ix_document_embedding_job_research_document_id",
        table_name="document_embedding_job",
        schema="nexus",
    )
    op.drop_index(
        "ix_document_embedding_job_document_extraction_id",
        table_name="document_embedding_job",
        schema="nexus",
    )
    op.drop_index(
        "ix_document_embedding_job_status", table_name="document_embedding_job", schema="nexus"
    )
    op.drop_table("document_embedding_job", schema="nexus")
