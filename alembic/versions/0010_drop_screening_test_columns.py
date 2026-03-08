"""drop test_pnl_pct and test_win_rate from screening_results

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("screening_results", "test_pnl_pct")
    op.drop_column("screening_results", "test_win_rate")


def downgrade() -> None:
    op.add_column("screening_results", sa.Column("test_win_rate", sa.Float(), nullable=False, server_default="0"))
    op.add_column("screening_results", sa.Column("test_pnl_pct", sa.Float(), nullable=False, server_default="0"))
