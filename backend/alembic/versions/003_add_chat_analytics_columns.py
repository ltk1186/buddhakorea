"""Add analytics columns to chat_messages

Revision ID: 003
Revises: 002
Create Date: 2026-04-01

Adds missing columns for chat analytics:
- tokens_used: Token count for billing/analytics
- latency_ms: Response generation time
- sources_json: JSON array of source references
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add missing analytics columns to chat_messages table."""

    # 002 already creates these columns on fresh installs. Legacy installations
    # stamped at 002 can still need this repair. Do not rewrite applied data.
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("chat_messages")}
    for column in (
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("sources_json", postgresql.JSON(), nullable=True),
    ):
        if column.name not in existing:
            op.add_column("chat_messages", column)


def downgrade() -> None:
    """002 owns these columns; preserve them when returning to 002."""
