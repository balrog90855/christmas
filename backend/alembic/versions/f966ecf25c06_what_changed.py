"""what changed

Revision ID: f966ecf25c06
Revises: 0002
Create Date: 2026-10-12 22:21:28.836726
"""
from alembic import op
import sqlalchemy as sa


revision = 'f966ecf25c06'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "charity_votes" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("charity_votes")}
    if "voter_key" not in columns:
        op.add_column("charity_votes", sa.Column("voter_key", sa.String(length=120), nullable=True))
        op.execute(
            "UPDATE charity_votes SET voter_key = "
            "(SELECT LOWER(TRIM(entries.employee_number)) FROM entries "
            "WHERE entries.id = charity_votes.entry_id) WHERE voter_key IS NULL"
        )
    if columns.get("voter_key", {}).get("nullable", True):
        op.alter_column(
            "charity_votes",
            "voter_key",
            existing_type=sa.VARCHAR(length=120),
            nullable=False,
        )

    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("charity_votes")
    }
    unique_columns.update(
        tuple(index["column_names"])
        for index in inspector.get_indexes("charity_votes")
        if index["unique"]
    )
    if ("voter_key",) not in unique_columns:
        op.create_unique_constraint(
            "uq_charity_votes_voter_key", "charity_votes", ["voter_key"]
        )

    entry_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys("charity_votes")
            if foreign_key["constrained_columns"] == ["entry_id"]
        ),
        None,
    )
    if entry_foreign_key is None or entry_foreign_key.get("options", {}).get("ondelete") != "RESTRICT":
        if entry_foreign_key and entry_foreign_key["name"]:
            op.drop_constraint(entry_foreign_key["name"], "charity_votes", type_="foreignkey")
        op.create_foreign_key(
            "fk_charity_votes_entry_id_entries",
            "charity_votes",
            "entries",
            ["entry_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "charity_votes" not in inspector.get_table_names():
        return

    entry_foreign_key = next(
        (
            foreign_key
            for foreign_key in inspector.get_foreign_keys("charity_votes")
            if foreign_key["constrained_columns"] == ["entry_id"]
        ),
        None,
    )
    if entry_foreign_key and entry_foreign_key["name"]:
        op.drop_constraint(entry_foreign_key["name"], "charity_votes", type_="foreignkey")
        op.create_foreign_key(
            "fk_charity_votes_entry_id_entries",
            "charity_votes",
            "entries",
            ["entry_id"],
            ["id"],
            ondelete="CASCADE",
        )

    unique_constraints = [
        constraint
        for constraint in inspector.get_unique_constraints("charity_votes")
        if constraint["column_names"] == ["voter_key"]
    ]
    for constraint in unique_constraints:
        if constraint["name"]:
            op.drop_constraint(constraint["name"], "charity_votes", type_="unique")
    for index in inspector.get_indexes("charity_votes"):
        if index["unique"] and index["column_names"] == ["voter_key"]:
            op.drop_index(index["name"], table_name="charity_votes")

    op.alter_column(
        "charity_votes",
        "voter_key",
        existing_type=sa.VARCHAR(length=120),
        nullable=True,
    )
