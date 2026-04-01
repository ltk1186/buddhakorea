"""Encrypt social account tokens for security

Revision ID: 005
Revises: 004
Create Date: 2026-03-28

Adds encrypted token columns and migrates existing plaintext tokens.
Keeps old columns for rollback safety during transition period.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add encrypted token columns."""

    # Add new encrypted token columns
    op.add_column(
        'social_accounts',
        sa.Column('access_token_encrypted', sa.Text(), nullable=True)
    )

    op.add_column(
        'social_accounts',
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True)
    )

    # Note: Migration script will handle copying and encrypting data
    # See: python -m alembic.versions.encrypt_migration for data migration


def downgrade() -> None:
    """Remove encrypted token columns."""

    op.drop_column('social_accounts', 'refresh_token_encrypted')
    op.drop_column('social_accounts', 'access_token_encrypted')
