"""Sprint 10 — add users.specialty for doctor directory and triage routing.

Revision ID: 20260624_000000
Revises: 20260623_000000
Create Date: 2026-06-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260624_000000"
down_revision = "20260623_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("specialty", sa.String(length=100), nullable=True),
        schema="public",
    )
    op.create_index(
        "idx_users_specialty", "users", ["specialty"], schema="public"
    )


def downgrade() -> None:
    op.drop_index("idx_users_specialty", table_name="users", schema="public")
    op.drop_column("users", "specialty", schema="public")
