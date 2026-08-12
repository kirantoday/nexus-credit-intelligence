"""research notes and audit event

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-12 08:50:35.188348

Milestone 10A (PLAN.md row 9, §4.10/§4.12/§24.12): `research_note` +
`research_note_version` (a dated, versioned investment thesis per
issuer/security, full-snapshot-per-edit) and `audit_event` (the first
concrete audited-write path in the app). No existing table changed.

No `user`/`role`/`user_role` tables — `AUTH_ENABLED=false` and no per-user
auth exists yet (TD-002); `research_note.author_user_id` and
`audit_event.user_id` are plain nullable `text`, mirroring
`collection.owner_user_id`'s already-established nullable-identity
convention (Milestone 8/ADR-016), not a FK to a table that doesn't exist.

`audit_event.event_type`/`entity_table` are intentionally left as
unconstrained `text` (no CHECK), unlike this milestone's other new enum-
shaped columns — see `app.models.audit`'s module docstring.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("entity_table", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("before_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_audit_event_entity",
        "audit_event",
        ["entity_table", "entity_id"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_audit_event_occurred_at", "audit_event", ["occurred_at"], unique=False, schema="nexus"
    )
    op.create_index(
        "ix_audit_event_user_id", "audit_event", ["user_id"], unique=False, schema="nexus"
    )
    op.create_table(
        "research_note",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("issuer_id", sa.UUID(), nullable=False),
        sa.Column("security_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("thesis_status", sa.Text(), nullable=False),
        sa.Column("conviction", sa.Text(), nullable=True),
        sa.Column("bull_case", sa.Text(), nullable=True),
        sa.Column("base_case", sa.Text(), nullable=True),
        sa.Column("bear_case", sa.Text(), nullable=True),
        sa.Column("catalysts", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("invalidation_conditions", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "access_classification",
            sa.Text(),
            server_default=sa.text("'standard'"),
            nullable=False,
        ),
        sa.Column("author_user_id", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "current_version_number", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
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
            "access_classification IN ('standard', 'restricted')",
            name="ck_research_note_access_classification",
        ),
        sa.CheckConstraint(
            "conviction IS NULL OR conviction IN ('low', 'medium', 'high')",
            name="ck_research_note_conviction",
        ),
        sa.CheckConstraint(
            "thesis_status IN ('draft', 'active', 'monitoring', 'invalidated', 'resolved')",
            name="ck_research_note_thesis_status",
        ),
        sa.CheckConstraint(
            "(is_archived AND archived_at IS NOT NULL) OR (NOT is_archived AND archived_at IS NULL)",
            name="ck_research_note_archived_requires_timestamp",
        ),
        sa.ForeignKeyConstraint(["issuer_id"], ["nexus.issuer.id"]),
        sa.ForeignKeyConstraint(["security_id"], ["nexus.security.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_research_note_is_archived",
        "research_note",
        ["is_archived"],
        unique=False,
        schema="nexus",
    )
    op.create_index(
        "ix_research_note_issuer_id", "research_note", ["issuer_id"], unique=False, schema="nexus"
    )
    op.create_index(
        "ix_research_note_security_id",
        "research_note",
        ["security_id"],
        unique=False,
        schema="nexus",
    )
    op.create_table(
        "research_note_version",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("research_note_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("thesis_status", sa.Text(), nullable=False),
        sa.Column("conviction", sa.Text(), nullable=True),
        sa.Column("bull_case", sa.Text(), nullable=True),
        sa.Column("base_case", sa.Text(), nullable=True),
        sa.Column("bear_case", sa.Text(), nullable=True),
        sa.Column("catalysts", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("invalidation_conditions", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("access_classification", sa.Text(), nullable=False),
        sa.Column("edited_by", sa.Text(), nullable=True),
        sa.Column(
            "edited_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "access_classification IN ('standard', 'restricted')",
            name="ck_research_note_version_access_classification",
        ),
        sa.CheckConstraint(
            "conviction IS NULL OR conviction IN ('low', 'medium', 'high')",
            name="ck_research_note_version_conviction",
        ),
        sa.CheckConstraint(
            "thesis_status IN ('draft', 'active', 'monitoring', 'invalidated', 'resolved')",
            name="ck_research_note_version_thesis_status",
        ),
        sa.ForeignKeyConstraint(["research_note_id"], ["nexus.research_note.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="nexus",
    )
    op.create_index(
        "ix_research_note_version_note_version",
        "research_note_version",
        ["research_note_id", "version_number"],
        unique=True,
        schema="nexus",
    )
    op.create_index(
        "ix_research_note_version_research_note_id",
        "research_note_version",
        ["research_note_id"],
        unique=False,
        schema="nexus",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_note_version_research_note_id",
        table_name="research_note_version",
        schema="nexus",
    )
    op.drop_index(
        "ix_research_note_version_note_version",
        table_name="research_note_version",
        schema="nexus",
    )
    op.drop_table("research_note_version", schema="nexus")
    op.drop_index("ix_research_note_security_id", table_name="research_note", schema="nexus")
    op.drop_index("ix_research_note_issuer_id", table_name="research_note", schema="nexus")
    op.drop_index("ix_research_note_is_archived", table_name="research_note", schema="nexus")
    op.drop_table("research_note", schema="nexus")
    op.drop_index("ix_audit_event_user_id", table_name="audit_event", schema="nexus")
    op.drop_index("ix_audit_event_occurred_at", table_name="audit_event", schema="nexus")
    op.drop_index("ix_audit_event_entity", table_name="audit_event", schema="nexus")
    op.drop_table("audit_event", schema="nexus")
