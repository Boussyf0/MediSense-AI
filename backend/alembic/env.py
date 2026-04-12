"""
Alembic environment — configures how migrations connect to the DB
and how they discover your SQLAlchemy models.

Two run modes:
  - offline: generates SQL script without connecting to DB (useful for review)
  - online:  connects to DB and applies migrations directly

Why async?
  We use asyncpg as our DB driver. Alembic needs a special async setup
  to work with it (run_async_migrations wraps everything in asyncio.run).
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Import your app's config and models ──────────────────
# This is the key line: by importing Base and all models,
# Alembic's autogenerate can detect schema changes automatically
from app.core.config import get_settings
from app.db.session import Base

# Import ALL models here so Base.metadata knows about them
# If you forget to import a model, Alembic won't track it
from app.db.models.user import User
from app.db.models.patient import Patient, PatientIdentity
from app.db.models.audit_log import AuditLog, ConsentLog   # Sprint 2

settings = get_settings()

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Override the sqlalchemy.url from alembic.ini with our real URL from .env
# This is why alembic.ini has a placeholder URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up logging from alembic.ini configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData object containing ALL table definitions
# Alembic compares this against the actual DB to find differences
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL statements to stdout without connecting to the DB.
    Useful for:
      - Reviewing what SQL will be executed before applying
      - Generating migration scripts for DBA review (medical compliance)
      - Environments where direct DB access is restricted
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include schemas (needed for our 'secure' schema)
        include_schemas=True,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="public",
        # compare_type=True: detect column type changes (e.g., VARCHAR(100) → VARCHAR(255))
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using async engine.

    NullPool is used here (not the app's connection pool) because:
      - Migrations run once as a script, not as a long-running service
      - Using NullPool prevents connection leaks after migration completes
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — wraps async in sync."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
