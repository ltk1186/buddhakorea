"""Baseline: existing schema (users, chat_sessions, chat_messages)

This migration represents the database state BEFORE the auth upgrade.
Run `alembic stamp 001` on existing databases to mark this as applied.

Revision ID: 001
Revises: None
Create Date: 2024-12-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create baseline tables if they don't exist (for fresh installs)."""

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('nickname', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=True),
        sa.Column('social_id', sa.String(length=255), nullable=True),
        sa.Column('profile_img', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_social_id', 'users', ['social_id'], unique=False)

    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_uuid', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_sessions_id', 'chat_sessions', ['id'], unique=False)
    op.create_index('ix_chat_sessions_session_uuid', 'chat_sessions', ['session_uuid'], unique=True)
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'], unique=False)

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('model_used', sa.String(length=50), nullable=True),
        sa.Column('sources_count', sa.Integer(), nullable=True),
        sa.Column('response_mode', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_id', 'chat_messages', ['id'], unique=False)
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'], unique=False)


def downgrade() -> None:
    """Drop all baseline tables."""
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions')
    op.drop_table('users')
