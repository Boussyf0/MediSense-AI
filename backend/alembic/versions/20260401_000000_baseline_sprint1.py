"""baseline_sprint1

This is a BASELINE migration — it does not create or modify any tables.
It marks the starting point for Alembic tracking.

The actual schema was created by scripts/init_db.sql on first DB start.
All future schema changes will be tracked as incremental migrations from here.

Tables in DB at this baseline (from init_db.sql):
  public.users               — staff accounts (doctors, secretaries, admins)
  public.patients            — pseudonymized patient records
  secure.patients_identity   — encrypted civil identity (RGPD)
  public.audit_logs          — immutable access log (RGPD Art.30)
  public.consent_logs        — immutable consent history (RGPD Art.7)
  public.appointments        — appointment scheduling

Sprint 2 will add ORM models + migrations for audit_logs, consent_logs, appointments.

Revision ID: s1_baseline_0001
Revises:
Create Date: 2026-04-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 's1_baseline_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline — nothing to do.
    The schema already exists from init_db.sql.
    """
    pass


def downgrade() -> None:
    """
    Cannot downgrade below baseline.
    To reset: docker compose down -v && docker compose up -d
    """
    pass
