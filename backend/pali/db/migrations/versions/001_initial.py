"""Initial migration - create tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create literatures table
    op.create_table(
        'literatures',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('pali_name', sa.String(255), nullable=False),
        sa.Column('pitaka', sa.String(50), nullable=False),
        sa.Column('nikaya', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), server_default='parsed'),
        sa.Column('total_segments', sa.Integer, server_default='0'),
        sa.Column('translated_segments', sa.Integer, server_default='0'),
        sa.Column('source_pdf', sa.String(255), nullable=True),
        sa.Column('hierarchy_labels', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create segments table
    op.create_table(
        'segments',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('literature_id', sa.String(100), sa.ForeignKey('literatures.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vagga_id', sa.Integer, nullable=True),
        sa.Column('vagga_name', sa.String(255), nullable=True),
        sa.Column('sutta_id', sa.Integer, nullable=True),
        sa.Column('sutta_name', sa.String(255), nullable=True),
        sa.Column('paragraph_id', sa.Integer, nullable=False),
        sa.Column('original_text', sa.Text, nullable=False),
        sa.Column('translation', postgresql.JSONB, nullable=True),
        sa.Column('is_translated', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create unique constraint on segment location
    op.create_unique_constraint(
        'uq_segment_location',
        'segments',
        ['literature_id', 'vagga_id', 'sutta_id', 'paragraph_id']
    )

    # Create indexes for segments
    op.create_index('idx_segments_literature', 'segments', ['literature_id'])
    op.create_index('idx_segments_location', 'segments', ['literature_id', 'vagga_id', 'sutta_id'])
    op.create_index('idx_segments_translated', 'segments', ['is_translated'])

    # Create query_logs table
    op.create_table(
        'query_logs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('literature_id', sa.String(100), sa.ForeignKey('literatures.id', ondelete='SET NULL'), nullable=True),
        sa.Column('segment_id', sa.Integer, nullable=True),
        sa.Column('question', sa.Text, nullable=False),
        sa.Column('answer', sa.Text, nullable=True),
        sa.Column('model', sa.String(50), nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Create indexes for query_logs
    op.create_index('idx_query_logs_session', 'query_logs', ['session_id'])
    op.create_index('idx_query_logs_created', 'query_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('query_logs')
    op.drop_table('segments')
    op.drop_table('literatures')
