"""Add trace_json to chat messages

Revision ID: 009
Revises: 008
Create Date: 2026-04-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trace_json to chat_messages for admin investigation."""
    op.add_column(
        "chat_messages",
        sa.Column("trace_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Remove trace_json from chat_messages."""
    op.drop_column("chat_messages", "trace_json")
