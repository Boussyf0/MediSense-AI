"""Sprint 6 — Salesforce CRM sync columns on appointments.

Revision ID: 20260608_000000
Revises: 20260602_000000
Create Date: 2026-06-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260608_000000"
down_revision = "20260602_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("crm_sync_status", sa.String(20), nullable=False, server_default="PENDING"),
        schema="public",
    )
    op.add_column(
        "appointments",
        sa.Column("crm_correlation_id", sa.String(64), nullable=True),
        schema="public",
    )
    op.add_column(
        "appointments",
        sa.Column("crm_retry_count", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        schema="public",
    )
    op.add_column(
        "appointments",
        sa.Column("crm_last_error", sa.Text(), nullable=True),
        schema="public",
    )
    op.add_column(
        "appointments",
        sa.Column("crm_synced_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    op.create_check_constraint(
        "appointments_crm_sync_status_check",
        "appointments",
        "crm_sync_status IN ('PENDING','SENT','FAILED','SKIPPED','CB_OPEN')",
        schema="public",
    )
    op.create_index(
        "idx_appointments_crm_retry",
        "appointments",
        ["crm_sync_status", "crm_retry_count"],
        schema="public",
        postgresql_where=sa.text("crm_sync_status = 'FAILED'"),
    )


def downgrade() -> None:
    op.drop_index("idx_appointments_crm_retry", table_name="appointments", schema="public")
    op.drop_constraint("appointments_crm_sync_status_check", "appointments", schema="public")
    op.drop_column("appointments", "crm_synced_at", schema="public")
    op.drop_column("appointments", "crm_last_error", schema="public")
    op.drop_column("appointments", "crm_retry_count", schema="public")
    op.drop_column("appointments", "crm_correlation_id", schema="public")
    op.drop_column("appointments", "crm_sync_status", schema="public")
