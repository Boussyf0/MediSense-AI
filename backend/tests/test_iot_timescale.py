"""
TimescaleDB hypertable smoke test (Sprint 7).

Skipped automatically when:
  - The DB connection is not PostgreSQL (e.g. SQLite-based unit runs).
  - The `timescaledb` extension is not installed (plain Postgres / Neon free).

Verifies that a 1 000-row insert + range query stays under 100 ms once the
hypertable is in place.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text


def _has_timescale_sync() -> bool:
    """Probe the sync test DB for the timescaledb extension."""
    try:
        from sqlalchemy import create_engine
        from app.core.config import get_settings

        settings = get_settings()
        url = settings.DATABASE_URL_SYNC.replace(
            settings.POSTGRES_DB, f"{settings.POSTGRES_DB}_test"
        )
        engine = create_engine(url)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'")
            ).fetchone()
        engine.dispose()
        return row is not None
    except Exception:
        return False


pytestmark = [
    pytest.mark.timescale,
    pytest.mark.skipif(
        not _has_timescale_sync(),
        reason="TimescaleDB extension not installed in test DB",
    ),
]


@pytest.mark.asyncio
async def test_biometric_reading_hypertable_query_under_100ms(test_db):
    """Insert 1 000 readings for a single patient, range-query should be fast."""
    from app.db.models.biometric_reading import BiometricReading

    patient_uuid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    rows = [
        BiometricReading(
            id=uuid.uuid4(),
            patient_uuid=patient_uuid,
            ts=now - timedelta(minutes=i),
            hr=70 + (i % 10),
            spo2=98,
            hrv=42,
        )
        for i in range(1000)
    ]
    test_db.add_all(rows)
    await test_db.flush()

    start = time.perf_counter()
    result = await test_db.execute(
        text(
            "SELECT count(*) FROM biometric_reading "
            "WHERE patient_uuid = :p AND ts > :since"
        ),
        {"p": str(patient_uuid), "since": now - timedelta(hours=12)},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    count = result.scalar_one()

    assert count == 720, f"expected 720 rows in last 12h, got {count}"
    assert elapsed_ms < 100, f"hypertable query took {elapsed_ms:.1f}ms (>100ms)"
