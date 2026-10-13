"""Add winners table for the raffle draw.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "winners" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "winners",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tile_number", sa.Integer, nullable=False, unique=True),
        sa.Column("entry_id", sa.Integer, sa.ForeignKey("entries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("prize_id", sa.Integer, sa.ForeignKey("prizes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prize_title", sa.String(120), nullable=True),
        sa.Column("drawn_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("winners")
