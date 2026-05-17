"""Add sell_only flag to trading_bots

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "trading_bots",
        sa.Column("sell_only", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("trading_bots", "sell_only")
