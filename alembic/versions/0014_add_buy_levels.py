"""Add buy_levels table

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "buy_levels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trading_bot_id", sa.Integer(), sa.ForeignKey("trading_bots.id"), nullable=False),
        sa.Column("level_index", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_buy_levels_trading_bot_id", "buy_levels", ["trading_bot_id"])
    op.create_index("ix_buy_levels_bot_level", "buy_levels", ["trading_bot_id", "level_index"], unique=True)


def downgrade():
    op.drop_table("buy_levels")
