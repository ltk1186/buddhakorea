"""Add token revocation mechanism for security

Revision ID: 006
Revises: 005
Create Date: 2026-03-28

Adds revoked_tokens table to track invalidated OAuth tokens:
- Allows users to logout and invalidate their tokens immediately
- Prevents reuse of tokens after account compromise or suspicious activity
- Supports different revocation reasons for audit logging
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create revoked_tokens table."""

    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('social_account_id', sa.Integer(), nullable=False),
        sa.Column('token_type', sa.String(20), nullable=False),  # 'access' or 'refresh'
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(255), nullable=True),  # 'logout', 'reauth', 'compromise', etc.
        sa.Column('metadata', postgresql.JSON(), nullable=True),  # Additional context
        sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_revoked_tokens_social_account_id', 'social_account_id'),
        sa.Index('idx_revoked_tokens_revoked_at', 'revoked_at'),
    )

    # Index for fast lookup: check if a token was revoked
    op.create_index(
        'idx_revoked_tokens_social_account_type',
        'revoked_tokens',
        ['social_account_id', 'token_type'],
        unique=False
    )


def downgrade() -> None:
    """Drop revoked_tokens table."""

    op.drop_index('idx_revoked_tokens_social_account_type', table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
