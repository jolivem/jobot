"""replace buy_percentage with grid_levels

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trading_bots", sa.Column("grid_levels", sa.Integer(), nullable=False, server_default="10"))
    op.drop_column("trading_bots", "buy_percentage")


def downgrade() -> None:
    op.add_column("trading_bots", sa.Column("buy_percentage", sa.Float(), nullable=False, server_default="2.0"))
    op.drop_column("trading_bots", "grid_levels")
