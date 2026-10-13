"""Baseline schema (safe to run on databases created before Alembic was added).

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())
    tstz = sa.DateTime(timezone=True)

    if "settings" not in existing:
        op.create_table(
            "settings",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("title", sa.String(120)),
            sa.Column("subtitle", sa.String(300)),
            sa.Column("cols", sa.Integer),
            sa.Column("rows", sa.Integer),
            sa.Column("price_pounds", sa.Integer),
            sa.Column("charity_percent", sa.Integer),
            sa.Column("charity_name", sa.String(120)),
            sa.Column("hold_days", sa.Integer),
            sa.Column("image_version", sa.Integer),
            sa.Column("image_file", sa.String(200), nullable=True),
        )
    if "entries" not in existing:
        op.create_table(
            "entries",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("employee_number", sa.String(40), nullable=False),
            sa.Column("email", sa.String(200), nullable=True),
            sa.Column("lockin_code", sa.String(16), nullable=False),
            sa.Column("status", sa.String(20)),
            sa.Column("failed_attempts", sa.Integer),
            sa.Column("created_at", tstz),
            sa.Column("expires_at", tstz, nullable=False),
            sa.Column("locked_at", tstz, nullable=True),
        )
    if "tiles" not in existing:
        op.create_table(
            "tiles",
            sa.Column("number", sa.Integer, primary_key=True),
            sa.Column("entry_id", sa.Integer, sa.ForeignKey("entries.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_tiles_entry_id", "tiles", ["entry_id"])
    if "prizes" not in existing:
        op.create_table(
            "prizes",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("position", sa.Integer),
            sa.Column("title", sa.String(120), nullable=False),
            sa.Column("description", sa.Text),
        )
    if "charities" not in existing:
        op.create_table(
            "charities",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("position", sa.Integer),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.String(500)),
        )
    if "charity_votes" not in existing:
        op.create_table(
            "charity_votes",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("entry_id", sa.Integer, sa.ForeignKey("entries.id", ondelete="RESTRICT"), nullable=False, unique=True),
            sa.Column("charity_id", sa.Integer, sa.ForeignKey("charities.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("voter_key", sa.String(120), nullable=False, unique=True),
            sa.Column("voted_at", tstz),
        )
    else:
        cols = {c["name"] for c in inspector.get_columns("charity_votes")}
        if "voter_key" not in cols:
            op.add_column("charity_votes", sa.Column("voter_key", sa.String(120), nullable=True))
            op.execute(
                "UPDATE charity_votes SET voter_key = (SELECT LOWER(TRIM(entries.employee_number)) "
                "FROM entries WHERE entries.id = charity_votes.entry_id) WHERE voter_key IS NULL"
            )
            op.create_index("uq_charity_votes_voter_key", "charity_votes", ["voter_key"], unique=True)


def downgrade() -> None:
    raise NotImplementedError("Baseline cannot be downgraded.")
