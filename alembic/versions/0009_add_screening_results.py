"""add screening_results table

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screening_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(50), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("best_pnl_pct", sa.Float(), nullable=False),
        sa.Column("best_min_price", sa.Float(), nullable=False),
        sa.Column("best_max_price", sa.Float(), nullable=False),
        sa.Column("best_grid_levels", sa.Integer(), nullable=False),
        sa.Column("best_sell_percentage", sa.Float(), nullable=False),
        sa.Column("num_trades", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=False),
        sa.Column("max_drawdown", sa.Float(), nullable=False),
        sa.Column("sharpe_ratio", sa.Float(), nullable=False),
        sa.Column("test_pnl_pct", sa.Float(), nullable=False),
        sa.Column("test_win_rate", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_screening_results_task_id", "screening_results", ["task_id"])
    op.create_index("ix_screening_results_user_id", "screening_results", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_screening_results_user_id", "screening_results")
    op.drop_index("ix_screening_results_task_id", "screening_results")
    op.drop_table("screening_results")
