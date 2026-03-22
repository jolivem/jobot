"""Add grid_level to trades

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("trades", sa.Column("grid_level", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("trades", "grid_level")
