"""Add admin query reviews

Revision ID: 010
Revises: 009
Create Date: 2026-04-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create admin_query_reviews table."""
    op.create_table(
        "admin_query_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index(op.f("ix_admin_query_reviews_id"), "admin_query_reviews", ["id"], unique=False)
    op.create_index(op.f("ix_admin_query_reviews_message_id"), "admin_query_reviews", ["message_id"], unique=False)


def downgrade() -> None:
    """Drop admin_query_reviews table."""
    op.drop_index(op.f("ix_admin_query_reviews_message_id"), table_name="admin_query_reviews")
    op.drop_index(op.f("ix_admin_query_reviews_id"), table_name="admin_query_reviews")
    op.drop_table("admin_query_reviews")
