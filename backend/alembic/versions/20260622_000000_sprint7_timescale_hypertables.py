"""Sprint 7 — convert biometric_reading and biometric_anomalies to TimescaleDB hypertables.

Revision ID: 20260622_000000
Revises: 20260615_000000
Create Date: 2026-06-22 00:00:00.000000

The migration is intentionally tolerant: if the `timescaledb` extension is
unavailable (e.g. plain PostgreSQL on Neon free tier, SQLite in unit tests),
the upgrade is a no-op and the tables stay regular relations.

Chunk interval: 7 days. Retention: 30 days for raw readings (anomalies kept
indefinitely so we can audit alerts after the fact).
"""
from alembic import op


revision = "20260622_000000"
down_revision = "20260615_000000"
branch_labels = None
depends_on = None


def _timescale_available(bind) -> bool:
    """Return True iff the timescaledb extension can be loaded on this server.

    Requires both that the extension files are present AND that
    `shared_preload_libraries` includes `timescaledb` — without the preload,
    `CREATE EXTENSION` crashes the backend connection.
    """
    if bind.dialect.name != "postgresql":
        return False
    available = bind.exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'"
    ).fetchone()
    if available is None:
        return False
    preload = bind.exec_driver_sql("SHOW shared_preload_libraries").scalar()
    return "timescaledb" in (preload or "")


def upgrade() -> None:
    bind = op.get_bind()
    if not _timescale_available(bind):
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # biometric_reading — high volume, 30-day retention
    op.execute(
        """
        SELECT create_hypertable(
            'public.biometric_reading',
            'ts',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE,
            migrate_data => TRUE
        )
        """
    )
    op.execute(
        """
        SELECT add_retention_policy(
            'public.biometric_reading',
            INTERVAL '30 days',
            if_not_exists => TRUE
        )
        """
    )

    # biometric_anomalies — keep forever (audit trail), still benefits from chunking
    op.execute(
        """
        SELECT create_hypertable(
            'public.biometric_anomalies',
            'detected_at',
            chunk_time_interval => INTERVAL '30 days',
            if_not_exists => TRUE,
            migrate_data => TRUE
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _timescale_available(bind):
        return

    # Drop retention policy first; ignore if absent
    op.execute(
        "SELECT remove_retention_policy('public.biometric_reading', if_exists => TRUE)"
    )
    # Hypertables remain queryable as plain tables after extension drop, so we
    # leave the rows in place; only the policy is reverted. A full revert would
    # require COPY-out/COPY-in, which is out of scope for this migration.
