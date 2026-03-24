"""Add lstm_bots table

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lstm_bots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeframes", sa.String(100), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("max_positions", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("buy_slope_threshold", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sell_slope_threshold", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("take_profit_pct", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column("stop_loss_pct", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column("model_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_lstm_bots_active", "lstm_bots", ["is_active", "user_id"])


def downgrade():
    op.drop_table("lstm_bots")
