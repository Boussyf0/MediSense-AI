"""Sprint 7 — device_token table for FCM push notifications (US-29).

Revision ID: 20260623_000000
Revises: 20260622_000000
Create Date: 2026-06-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260623_000000"
down_revision = "20260622_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_token",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_uuid"], ["public.users.user_uuid"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("token", name="uq_device_token_token"),
        schema="public",
    )
    op.create_index(
        "idx_device_token_user", "device_token", ["user_uuid"], schema="public"
    )


def downgrade() -> None:
    op.drop_index("idx_device_token_user", table_name="device_token", schema="public")
    op.drop_table("device_token", schema="public")
