"""Make pnl_snapshots.trading_bot_id nullable

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "pnl_snapshots",
        "trading_bot_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    op.execute("UPDATE pnl_snapshots SET trading_bot_id = 0 WHERE trading_bot_id IS NULL")
    op.alter_column(
        "pnl_snapshots",
        "trading_bot_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
