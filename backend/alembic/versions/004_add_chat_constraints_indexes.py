"""Add constraints and indexes for ChatSession denormalization

Revision ID: 004
Revises: 003
Create Date: 2026-03-28

Adds:
- CHECK constraint on chat_sessions.message_count (>= 0)
- Index on (user_id, last_message_at DESC) for sorting by recency
- Index on (user_id, is_active) for active session filtering
- Index on (session_id, created_at DESC) for fast message retrieval
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add constraints and indexes for chat denormalization."""

    # Add CHECK constraint for message_count
    op.create_check_constraint(
        'chat_sessions_message_count_non_negative',
        'chat_sessions',
        'message_count >= 0'
    )

    # Add indexes for efficient session queries
    op.create_index(
        'idx_chat_sessions_user_id_last_message_at',
        'chat_sessions',
        ['user_id', sa.desc('last_message_at')],
        unique=False
    )

    op.create_index(
        'idx_chat_sessions_user_id_is_active',
        'chat_sessions',
        ['user_id', 'is_active'],
        unique=False
    )

    # Add index for fast message retrieval
    op.create_index(
        'idx_chat_messages_session_id_created_at',
        'chat_messages',
        ['session_id', sa.desc('created_at')],
        unique=False
    )


def downgrade() -> None:
    """Remove constraints and indexes."""

    op.drop_index('idx_chat_messages_session_id_created_at', table_name='chat_messages')
    op.drop_index('idx_chat_sessions_user_id_is_active', table_name='chat_sessions')
    op.drop_index('idx_chat_sessions_user_id_last_message_at', table_name='chat_sessions')
    op.drop_constraint('chat_sessions_message_count_non_negative', 'chat_sessions', type_='check')
