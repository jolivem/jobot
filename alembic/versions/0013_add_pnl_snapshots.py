"""Add pnl_snapshots table

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pnl_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("trading_bot_id", sa.Integer(), sa.ForeignKey("trading_bots.id"), nullable=False, index=True),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("total_pnl", sa.Float(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pnl_snapshots_user_time", "pnl_snapshots", ["user_id", "snapshot_at"])
    op.create_index("ix_pnl_snapshots_bot_time", "pnl_snapshots", ["trading_bot_id", "snapshot_at"], unique=True)


def downgrade():
    op.drop_table("pnl_snapshots")
