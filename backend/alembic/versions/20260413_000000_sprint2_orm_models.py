"""sprint2_orm_models

Sprint 2 — Register AuditLog and ConsentLog ORM models with Alembic.

This migration does NOT create any tables — they already exist from
scripts/init_db.sql (run on first Docker start).

What this migration DOES:
  - Establishes Alembic's baseline awareness of audit_logs and consent_logs
  - Future migrations can now reference these tables via autogenerate
  - Alembic will detect column additions/renames from Sprint 3 onwards

Why no CREATE TABLE statements?
  The tables were created in init_db.sql, not by a previous Alembic migration.
  Creating them here would fail with "table already exists".
  The correct approach: register them in the ORM metadata (done in env.py)
  and write a no-op migration as a tracking checkpoint.

If you ever need to rebuild from scratch:
  docker compose down -v && docker compose up -d
  alembic upgrade head

Revision ID: s2_models_0002
Revises: s1_baseline_0001
Create Date: 2026-04-13 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 's2_models_0002'
down_revision: Union[str, None] = 's1_baseline_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    No schema changes — tables already exist from init_db.sql.
    This migration registers the ORM models in Alembic's revision chain.
    """
    pass


def downgrade() -> None:
    """
    No-op downgrade — we do not drop audit/consent tables.
    These are immutable audit trails required for RGPD compliance.
    Dropping them would violate Art. 30 record-keeping obligations.
    """
    pass
