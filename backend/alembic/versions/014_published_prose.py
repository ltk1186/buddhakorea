"""Allow ordinary prose passages in published works without labeling them verses."""

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_source_kind", "canonical_sources", type_="check")
    op.create_check_constraint(
        "ck_source_kind",
        "canonical_sources",
        "kind IN ('verse', 'passage', 'supplement', 'appendix')",
    )


def downgrade() -> None:
    raise RuntimeError("Keep published prose intact; roll back application code instead.")
