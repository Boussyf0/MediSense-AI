"""Make biometric_reading.hrv nullable.

Mi Fitness does not publish HRV to Health Connect — the column must accept NULL
so that HR + SpO2 from Mi Band 7 Pro (and any other source missing HRV) can be
ingested. The simulator and the upcoming Gadgetbridge companion still write
all three.

Revision ID: 20260625_000000
Revises: 20260624_000000
Create Date: 2026-06-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260625_000000"
down_revision = "20260624_000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "biometric_reading",
        "hrv",
        existing_type=sa.Integer(),
        nullable=True,
        schema="public",
    )


def downgrade() -> None:
    op.alter_column(
        "biometric_reading",
        "hrv",
        existing_type=sa.Integer(),
        nullable=False,
        schema="public",
    )
