"""Sprint 5 — Smart SMS reminders for no-show prevention.

Revision ID: 20260602_000000
Revises: 20260525_000000
Create Date: 2026-06-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260602_000000"
down_revision = "20260525_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("sms_opt_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="public",
    )

    op.add_column(
        "appointments",
        sa.Column("sms_reminders_sent", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        schema="public",
    )
    op.add_column(
        "appointments",
        sa.Column("last_sms_reminder_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    op.create_check_constraint(
        "appointments_sms_reminders_sent_check",
        "appointments",
        "sms_reminders_sent >= 0 AND sms_reminders_sent <= 2",
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint("appointments_sms_reminders_sent_check", "appointments", schema="public")
    op.drop_column("appointments", "last_sms_reminder_at", schema="public")
    op.drop_column("appointments", "sms_reminders_sent", schema="public")
    op.drop_column("patients", "sms_opt_out", schema="public")
