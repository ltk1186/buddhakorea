"""Add admin audit logs table

Revision ID: 008
Revises: 007
Create Date: 2026-04-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create admin audit logs table."""
    op.create_table(
        'admin_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('admin_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=100), nullable=True),
        sa.Column('before_state', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('after_state', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_hash', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index('idx_admin_audit_logs_admin_user_id', 'admin_audit_logs', ['admin_user_id'], unique=False)
    op.create_index('idx_admin_audit_logs_action', 'admin_audit_logs', ['action'], unique=False)


def downgrade() -> None:
    """Drop admin audit logs table."""
    op.drop_index('idx_admin_audit_logs_action', table_name='admin_audit_logs')
    op.drop_index('idx_admin_audit_logs_admin_user_id', table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
