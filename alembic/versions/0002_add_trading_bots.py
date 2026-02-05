"""add trading_bots table

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trading_bots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_price", sa.Float(), nullable=False),
        sa.Column("min_price", sa.Float(), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("sell_percentage", sa.Float(), nullable=False),
        sa.Column("buy_percentage", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_trading_bots_user_id", "trading_bots", ["user_id"])
    op.create_index("ix_trading_bots_symbol", "trading_bots", ["symbol"])
    op.create_index("ix_trading_bots_active", "trading_bots", ["is_active", "user_id"])


def downgrade() -> None:
    op.drop_table("trading_bots")
