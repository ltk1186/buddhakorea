"""Versioned XML sources and published translations.

Revision ID: 013
Revises: 012
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "literatures",
        sa.Column("content_type", sa.String(20), nullable=False, server_default="legacy"),
    )
    op.create_table(
        "canonical_sources",
        sa.Column("stable_key", sa.String(160), primary_key=True),
        sa.Column(
            "segment_id",
            sa.Integer(),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "literature_id",
            sa.String(100),
            sa.ForeignKey("literatures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("chapter", sa.Integer()),
        sa.Column("verse", sa.Integer()),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("source_metadata", JSONB(), nullable=False),
        sa.UniqueConstraint("literature_id", "sort_order", name="uq_canonical_source_order"),
        sa.CheckConstraint("kind IN ('verse', 'supplement', 'appendix')", name="ck_source_kind"),
    )
    op.create_index(
        "ix_canonical_chapter", "canonical_sources", ["literature_id", "chapter", "sort_order"]
    )
    op.create_table(
        "translation_releases",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column(
            "literature_id",
            sa.String(100),
            sa.ForeignKey("literatures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("source_commit", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("id", "literature_id", name="uq_release_literature"),
    )
    op.create_index("ix_translation_release_literature", "translation_releases", ["literature_id"])
    op.create_table(
        "released_translations",
        sa.Column(
            "release_id",
            sa.String(100),
            sa.ForeignKey("translation_releases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "source_key",
            sa.String(160),
            sa.ForeignKey("canonical_sources.stable_key", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index("ix_released_translation_source", "released_translations", ["source_key"])
    op.create_table(
        "literature_publications",
        sa.Column(
            "literature_id",
            sa.String(100),
            sa.ForeignKey("literatures.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("release_id", sa.String(100), nullable=False),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["release_id", "literature_id"],
            ["translation_releases.id", "translation_releases.literature_id"],
        ),
    )
    op.create_index(
        "ix_publication_release", "literature_publications", ["release_id", "literature_id"]
    )


def downgrade() -> None:
    raise RuntimeError(
        "013 contains translation releases; unpublish or select an earlier release instead of dropping data."
    )
