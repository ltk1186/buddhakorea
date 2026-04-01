"""Add performance indexes for frequent queries

Revision ID: 007
Revises: 006
Create Date: 2026-03-28

Adds indexes to eliminate sequential table scans:
- Users: email lookup for OAuth callbacks
- SocialAccounts: provider lookup
- ChatMessages: session_id for message retrieval
- ChatSessions: user_id for session list
- UserUsage: user_id + date for quota queries
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes."""

    # Users table - fast OAuth callback lookup
    op.create_index(
        'idx_users_email',
        'users',
        ['email'],
        unique=True
    )

    # SocialAccounts - fast provider user lookup
    op.create_index(
        'idx_social_accounts_provider_user_id',
        'social_accounts',
        ['provider', 'provider_user_id'],
        unique=True
    )

    # ChatSessions - fast user session list
    op.create_index(
        'idx_chat_sessions_user_id_created_at',
        'chat_sessions',
        ['user_id', sa.desc('created_at')],
        unique=False
    )

    # UserUsage - fast quota lookups
    op.create_index(
        'idx_user_usage_user_id_date',
        'user_usage',
        ['user_id', 'usage_date'],
        unique=True
    )

    # AnonymousUsage - fast quota lookups by IP
    op.create_index(
        'idx_anonymous_usage_ip_hash_date',
        'anonymous_usage',
        ['ip_hash', 'usage_date'],
        unique=True
    )


def downgrade() -> None:
    """Remove performance indexes."""

    op.drop_index('idx_anonymous_usage_ip_hash_date', table_name='anonymous_usage')
    op.drop_index('idx_user_usage_user_id_date', table_name='user_usage')
    op.drop_index('idx_chat_sessions_user_id_created_at', table_name='chat_sessions')
    op.drop_index('idx_social_accounts_provider_user_id', table_name='social_accounts')
    op.drop_index('idx_users_email', table_name='users')
