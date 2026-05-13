"""Sprint 9/10 — IoT vitals + medication reminders + no-show feedback + SMS log.

Revision ID: 20260615_000000
Revises: 20260608_000000
Create Date: 2026-06-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260615_000000"
down_revision = "20260608_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "biometric_reading",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hr", sa.Integer(), nullable=False),
        sa.Column("spo2", sa.Integer(), nullable=False),
        sa.Column("hrv", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["patient_uuid"], ["public.patients.patient_uuid"]),
        schema="public",
    )
    op.create_index(
        "idx_biometric_reading_patient_ts",
        "biometric_reading",
        ["patient_uuid", "ts"],
        schema="public",
    )

    op.create_table(
        "iot_device",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("paired", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("battery", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["patient_uuid"], ["public.patients.patient_uuid"]),
        sa.UniqueConstraint("patient_uuid"),
        schema="public",
    )

    op.create_table(
        "medication_reminder",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("dosage", sa.String(length=80), nullable=False),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column("days_of_week", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["patient_uuid"], ["public.patients.patient_uuid"]),
        schema="public",
    )
    op.create_index(
        "idx_medication_reminder_patient",
        "medication_reminder",
        ["patient_uuid"],
        schema="public",
    )

    op.create_table(
        "noshow_feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("appointment_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("recorded_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["appointment_uuid"], ["public.appointments.appointment_uuid"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["public.users.user_uuid"]),
        schema="public",
    )
    op.create_index(
        "idx_noshow_feedback_appointment",
        "noshow_feedback",
        ["appointment_uuid"],
        schema="public",
    )

    op.create_table(
        "sms_reminder_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("appointment_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False, server_default="sms_reminder"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["appointment_uuid"], ["public.appointments.appointment_uuid"]),
        schema="public",
    )
    op.create_index(
        "idx_sms_reminder_log_appt_date",
        "sms_reminder_log",
        ["appointment_uuid", "scheduled_date"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_index("idx_sms_reminder_log_appt_date", table_name="sms_reminder_log", schema="public")
    op.drop_table("sms_reminder_log", schema="public")
    op.drop_index("idx_noshow_feedback_appointment", table_name="noshow_feedback", schema="public")
    op.drop_table("noshow_feedback", schema="public")
    op.drop_index("idx_medication_reminder_patient", table_name="medication_reminder", schema="public")
    op.drop_table("medication_reminder", schema="public")
    op.drop_table("iot_device", schema="public")
    op.drop_index("idx_biometric_reading_patient_ts", table_name="biometric_reading", schema="public")
    op.drop_table("biometric_reading", schema="public")
