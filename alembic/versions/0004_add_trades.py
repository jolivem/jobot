"""add trades table

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trading_bot_id", sa.Integer(), nullable=False),
        sa.Column("trade_type", sa.String(10), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["trading_bot_id"], ["trading_bots.id"]),
    )
    op.create_index("ix_trades_trading_bot_id", "trades", ["trading_bot_id"])
    op.create_index("ix_trades_created_at", "trades", ["created_at"])


def downgrade() -> None:
    op.drop_table("trades")
