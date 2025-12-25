"""Add page_number to segments

Revision ID: 002_add_page_number
Revises: 001_initial
Create Date: 2025-12-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_page_number"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("segments", sa.Column("page_number", sa.Integer(), nullable=True))
    op.create_index("idx_segments_page", "segments", ["literature_id", "page_number"])


def downgrade() -> None:
    op.drop_index("idx_segments_page", table_name="segments")
    op.drop_column("segments", "page_number")

