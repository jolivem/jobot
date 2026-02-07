"""add missing trading bot columns

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-07
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trading_bots", sa.Column("max_price", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trading_bots", sa.Column("min_price", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trading_bots", sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trading_bots", sa.Column("sell_percentage", sa.Float(), nullable=False, server_default="0"))
    op.add_column("trading_bots", sa.Column("buy_percentage", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("trading_bots", "buy_percentage")
    op.drop_column("trading_bots", "sell_percentage")
    op.drop_column("trading_bots", "total_amount")
    op.drop_column("trading_bots", "min_price")
    op.drop_column("trading_bots", "max_price")
