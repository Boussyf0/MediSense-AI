"""Bootstrap the database schema from the ORM models.

Used as the Fly release_command. The alembic migration chain is currently broken
for a from-scratch run (the migration that creates `public.patients` is chained
*after* migrations that foreign-key to it). The test suite builds its schema with
``Base.metadata.create_all`` (see tests/conftest.py), so that is the real source
of truth — we replicate it here.

Idempotent: extensions/schema use IF NOT EXISTS and create_all skips tables that
already exist, so it is safe to run on every deploy.

TODO: repair the migration history, then switch release_command back to
``alembic upgrade head``.
"""

from sqlalchemy import create_engine, text

import app.db.models  # noqa: F401 — importing registers every table on Base.metadata
from app.core.config import get_settings
from app.db.session import Base


def main() -> None:
    engine = create_engine(get_settings().DATABASE_URL_SYNC)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS secure"))
    Base.metadata.create_all(engine)
    print("✓ database schema ready")


if __name__ == "__main__":
    main()
