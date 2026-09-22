"""Adopt legacy application tables without replacing existing content.

Revision ID: 012
Revises: 011

Frozen definitions: do not import live ORM models into migrations. Existing
tables were previously created outside the central Alembic chain.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON, JSONB

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def _create_or_validate(name: str, *elements) -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(name):
        op.create_table(name, *elements)
        return
    existing = {column["name"] for column in inspector.get_columns(name)}
    expected = {column.name for column in elements if isinstance(column, sa.Column)}
    missing = expected - existing
    if missing:
        raise RuntimeError(f"Unexpected legacy schema: {name} missing {sorted(missing)}")


def _index(name: str, table: str, columns: list[str]) -> None:
    existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("literatures"):
        columns = {column["name"] for column in inspector.get_columns("literatures")}
        if "display_metadata" not in columns:
            op.add_column(
                "literatures",
                sa.Column(
                    "display_metadata",
                    JSONB(),
                    nullable=False,
                    server_default=sa.text("'{}'::jsonb"),
                ),
            )
    if inspector.has_table("segments"):
        columns = {column["name"] for column in inspector.get_columns("segments")}
        if "page_number" not in columns:
            op.add_column("segments", sa.Column("page_number", sa.Integer()))

    _create_or_validate(
        "literatures",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pali_name", sa.String(255), nullable=False),
        sa.Column("pitaka", sa.String(50), nullable=False),
        sa.Column("nikaya", sa.String(100)),
        sa.Column("status", sa.String(20)),
        sa.Column("total_segments", sa.Integer()),
        sa.Column("translated_segments", sa.Integer()),
        sa.Column("source_pdf", sa.String(255)),
        sa.Column("hierarchy_labels", JSONB()),
        sa.Column(
            "display_metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    _create_or_validate(
        "segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "literature_id",
            sa.String(100),
            sa.ForeignKey("literatures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vagga_id", sa.Integer()),
        sa.Column("vagga_name", sa.String(255)),
        sa.Column("sutta_id", sa.Integer()),
        sa.Column("sutta_name", sa.String(255)),
        sa.Column("page_number", sa.Integer()),
        sa.Column("paragraph_id", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("translation", JSONB()),
        sa.Column("is_translated", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint(
            "literature_id", "vagga_id", "sutta_id", "paragraph_id", name="uq_segment_location"
        ),
    )
    _create_or_validate(
        "query_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(100)),
        sa.Column(
            "literature_id", sa.String(100), sa.ForeignKey("literatures.id", ondelete="SET NULL")
        ),
        sa.Column("segment_id", sa.Integer()),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("model", sa.String(50)),
        sa.Column("tokens_used", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
    )
    _create_or_validate(
        "saved_exchanges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources_json", JSON()),
        sa.Column("model_used", sa.String(50)),
        sa.Column("response_mode", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    # Some installations were stamped past 006 without this table.
    _create_or_validate(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "social_account_id",
            sa.Integer(),
            sa.ForeignKey("social_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_type", sa.String(20), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(255)),
        sa.Column("metadata", JSON()),
    )
    for name, table, columns in (
        ("idx_segments_literature", "segments", ["literature_id"]),
        ("idx_segments_location", "segments", ["literature_id", "vagga_id", "sutta_id"]),
        ("idx_segments_page", "segments", ["page_number"]),
        ("idx_segments_translated", "segments", ["is_translated"]),
        ("idx_query_logs_session", "query_logs", ["session_id"]),
        ("idx_query_logs_created", "query_logs", ["created_at"]),
        ("ix_saved_exchanges_id", "saved_exchanges", ["id"]),
        ("ix_saved_exchanges_user_id", "saved_exchanges", ["user_id"]),
        ("idx_revoked_tokens_social_account_id", "revoked_tokens", ["social_account_id"]),
        ("idx_revoked_tokens_revoked_at", "revoked_tokens", ["revoked_at"]),
        (
            "idx_revoked_tokens_social_account_type",
            "revoked_tokens",
            ["social_account_id", "token_type"],
        ),
    ):
        _index(name, table, columns)


def downgrade() -> None:
    # These tables may contain pre-existing production data. Their ownership
    # cannot be inferred from the revision number, so never drop them here.
    raise RuntimeError(
        "012 adopts existing data tables; roll back application code, not this schema."
    )
