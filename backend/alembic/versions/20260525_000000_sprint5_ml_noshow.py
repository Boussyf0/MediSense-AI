"""Sprint 5 — ML No-Show predictive model support.

User stories covered:
  US-17: Features for ML (already in patients/appointments)
  US-20: ML Feedback loop for future retraining (ml_feedback table)
  US-21: ERD compliance for appointment status

Revision ID: 20260525_000000
Revises: 20260511_000000
Create Date: 2026-05-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "20260525_000000"
down_revision = "20260511_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ml_feedback (US-20) ──────────────────────────────────────────────────
    # Closes the MLOps loop for future retraining.
    op.create_table(
        "ml_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("appointment_uuid", UUID(as_uuid=True), nullable=False),
        sa.Column("was_predicted_correctly", sa.Boolean(), nullable=True),
        sa.Column("actual_status", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=20), nullable=False),
        sa.Column("prediction_prob", sa.Float(), nullable=False),
        sa.Column("doctor_feedback", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["appointment_uuid"], ["public.appointments.appointment_uuid"]),
        sa.UniqueConstraint("appointment_uuid"),
        schema="public"
    )

    # ── Align Appointment Status with Sprint 5 ERD (US-21) ────────────────────
    # User requested: PENDING, CONFIRMED, CANCELLED, COMPLETED, NO_SHOW
    # Current (from init_db): scheduled, confirmed, cancelled, completed, no_show
    
    # 1. Update existing data (lowercase to uppercase, scheduled to PENDING)
    op.execute("UPDATE public.appointments SET status = 'PENDING' WHERE status = 'scheduled'")
    op.execute("UPDATE public.appointments SET status = 'CONFIRMED' WHERE status = 'confirmed'")
    op.execute("UPDATE public.appointments SET status = 'CANCELLED' WHERE status = 'cancelled'")
    op.execute("UPDATE public.appointments SET status = 'COMPLETED' WHERE status = 'completed'")
    op.execute("UPDATE public.appointments SET status = 'NO_SHOW' WHERE status = 'no_show'")

    # 2. Update Check Constraint
    # Note: We need to drop the old constraint first. The name in init_db.sql was implicit.
    # PostgreSQL usually names it {table}_{column}_check
    op.execute("ALTER TABLE public.appointments DROP CONSTRAINT IF EXISTS appointments_status_check")
    op.create_check_constraint(
        "appointments_status_check",
        "appointments",
        "status IN ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'NO_SHOW')",
        schema="public"
    )


def downgrade() -> None:
    # Drop the feedback table
    op.drop_table("ml_feedback", schema="public")

    # Revert status to lowercase and scheduled
    op.execute("UPDATE public.appointments SET status = 'scheduled' WHERE status = 'PENDING'")
    op.execute("UPDATE public.appointments SET status = 'confirmed' WHERE status = 'CONFIRMED'")
    op.execute("UPDATE public.appointments SET status = 'cancelled' WHERE status = 'CANCELLED'")
    op.execute("UPDATE public.appointments SET status = 'completed' WHERE status = 'COMPLETED'")
    op.execute("UPDATE public.appointments SET status = 'no_show' WHERE status = 'NO_SHOW'")

    # Revert Check Constraint
    op.execute("ALTER TABLE public.appointments DROP CONSTRAINT IF EXISTS appointments_status_check")
    op.create_check_constraint(
        "appointments_status_check",
        "appointments",
        "status IN ('scheduled', 'confirmed', 'cancelled', 'completed', 'no_show')",
        schema="public"
    )
