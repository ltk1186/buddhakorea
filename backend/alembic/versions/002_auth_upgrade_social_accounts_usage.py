"""Auth upgrade: add social_accounts, user_usage, anonymous_usage tables and new columns

Revision ID: 002
Revises: 001
Create Date: 2024-12-22

Changes:
- Add social_accounts table for multi-provider OAuth
- Add user_usage table for logged-in user quotas
- Add anonymous_usage table for IP-based quotas
- Add new columns to users table (role, is_active, daily_chat_limit, updated_at)
- Add new columns to chat_sessions table (summary, is_archived, message_count, deleted_at)
- Add new columns to chat_messages table (sources_json, tokens_used, latency_ms)
- Migrate existing provider/social_id data to social_accounts
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add new tables and columns for auth upgrade."""

    # Detect dialect for JSON column compatibility
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Use appropriate JSON type
    if dialect == 'postgresql':
        json_type = postgresql.JSON()
    else:
        json_type = sa.JSON()

    # ========================================
    # 1. Add new columns to users table
    # ========================================
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=True, server_default='user'))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('users', sa.Column('daily_chat_limit', sa.Integer(), nullable=True, server_default='20'))
    op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Set defaults for existing rows
    op.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
    op.execute("UPDATE users SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE users SET daily_chat_limit = 20 WHERE daily_chat_limit IS NULL")

    # ========================================
    # 2. Create social_accounts table
    # ========================================
    op.create_table(
        'social_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('provider_user_id', sa.String(length=255), nullable=False),
        sa.Column('provider_email', sa.String(length=255), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('raw_profile', json_type, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user_id')
    )
    op.create_index('ix_social_accounts_id', 'social_accounts', ['id'], unique=False)
    op.create_index('ix_social_accounts_user_id', 'social_accounts', ['user_id'], unique=False)
    op.create_index('ix_social_accounts_lookup', 'social_accounts', ['provider', 'provider_user_id'], unique=False)

    # ========================================
    # 3. Migrate existing provider/social_id data to social_accounts
    # ========================================
    op.execute("""
        INSERT INTO social_accounts (user_id, provider, provider_user_id, provider_email, created_at, last_used_at)
        SELECT id, provider, social_id, email, created_at, last_login
        FROM users
        WHERE provider IS NOT NULL AND social_id IS NOT NULL
    """)

    # ========================================
    # 4. Create user_usage table
    # ========================================
    op.create_table(
        'user_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('usage_date', sa.Date(), nullable=False),
        sa.Column('chat_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tokens_used', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'usage_date', name='uq_user_usage_date')
    )
    op.create_index('ix_user_usage_id', 'user_usage', ['id'], unique=False)
    op.create_index('ix_user_usage_user_id', 'user_usage', ['user_id'], unique=False)
    op.create_index('ix_user_usage_lookup', 'user_usage', ['user_id', 'usage_date'], unique=False)

    # ========================================
    # 5. Create anonymous_usage table
    # ========================================
    op.create_table(
        'anonymous_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_hash', sa.String(length=64), nullable=False),
        sa.Column('usage_date', sa.Date(), nullable=False),
        sa.Column('chat_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ip_hash', 'usage_date', name='uq_anon_ip_date')
    )
    op.create_index('ix_anonymous_usage_id', 'anonymous_usage', ['id'], unique=False)
    op.create_index('ix_anonymous_usage_ip_hash', 'anonymous_usage', ['ip_hash'], unique=False)
    op.create_index('ix_anonymous_usage_lookup', 'anonymous_usage', ['ip_hash', 'usage_date'], unique=False)

    # ========================================
    # 6. Add new columns to chat_sessions table
    # ========================================
    op.add_column('chat_sessions', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('chat_sessions', sa.Column('is_archived', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('chat_sessions', sa.Column('message_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('chat_sessions', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # Update message_count from actual message counts
    op.execute("""
        UPDATE chat_sessions SET message_count = (
            SELECT COUNT(*) FROM chat_messages WHERE chat_messages.session_id = chat_sessions.id
        )
    """)

    # ========================================
    # 7. Add new columns to chat_messages table
    # ========================================
    op.add_column('chat_messages', sa.Column('sources_json', json_type, nullable=True))
    op.add_column('chat_messages', sa.Column('tokens_used', sa.Integer(), nullable=True))
    op.add_column('chat_messages', sa.Column('latency_ms', sa.Integer(), nullable=True))

    # ========================================
    # 8. Update foreign key constraints with proper ON DELETE behavior
    # ========================================
    # This is optional - only needed if you want to change existing FK behavior
    # op.drop_constraint('chat_sessions_user_id_fkey', 'chat_sessions', type_='foreignkey')
    # op.create_foreign_key(None, 'chat_sessions', 'users', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Revert auth upgrade changes."""

    # Remove new columns from chat_messages
    op.drop_column('chat_messages', 'latency_ms')
    op.drop_column('chat_messages', 'tokens_used')
    op.drop_column('chat_messages', 'sources_json')

    # Remove new columns from chat_sessions
    op.drop_column('chat_sessions', 'deleted_at')
    op.drop_column('chat_sessions', 'message_count')
    op.drop_column('chat_sessions', 'is_archived')
    op.drop_column('chat_sessions', 'summary')

    # Drop anonymous_usage table
    op.drop_table('anonymous_usage')

    # Drop user_usage table
    op.drop_table('user_usage')

    # Drop social_accounts table
    op.drop_table('social_accounts')

    # Remove new columns from users
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'daily_chat_limit')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'role')
