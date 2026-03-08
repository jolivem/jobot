"""Add matched_buy_trade_id to trades

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("trades", sa.Column("matched_buy_trade_id", sa.Integer(), sa.ForeignKey("trades.id"), nullable=True))


def downgrade():
    op.drop_column("trades", "matched_buy_trade_id")
