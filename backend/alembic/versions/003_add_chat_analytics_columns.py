"""Add analytics columns to chat_messages

Revision ID: 003
Revises: 002
Create Date: 2026-04-01

Adds missing columns for chat analytics:
- tokens_used: Token count for billing/analytics
- latency_ms: Response generation time
- sources_json: JSON array of source references
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing analytics columns to chat_messages table."""

    # Add tokens_used column
    op.add_column(
        'chat_messages',
        sa.Column('tokens_used', sa.Integer(), nullable=True),
    )

    # Add latency_ms column
    op.add_column(
        'chat_messages',
        sa.Column('latency_ms', sa.Integer(), nullable=True),
    )

    # Add sources_json column
    op.add_column(
        'chat_messages',
        sa.Column('sources_json', postgresql.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove analytics columns from chat_messages table."""

    op.drop_column('chat_messages', 'sources_json')
    op.drop_column('chat_messages', 'latency_ms')
    op.drop_column('chat_messages', 'tokens_used')
