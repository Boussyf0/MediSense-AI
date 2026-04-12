"""
Pytest fixtures — shared across all test files.

EVENT LOOP STRATEGY:
  Session-scoped ASYNC fixtures in pytest-asyncio 0.24 require the event_loop
  to also be session-scoped — causing "ScopeMismatch" errors when the default
  loop scope is function. And session-scoped event loops cause asyncpg
  connections to be shared across concurrent test tasks.

  Solution: separate responsibilities by sync vs async:

    db_schema  (session-scoped SYNC) — creates/drops tables ONCE per run
               using psycopg2 (sync driver). No event loop involved.
               Safe to be session-scoped without any asyncio concerns.

    test_db    (function-scoped ASYNC) — creates a FRESH async engine +
               session per test. All asyncpg connections live in the test's
               own per-test event loop. Rolls back at teardown.

    client     (function-scoped ASYNC) — wraps test_db.

This gives us:
  - Schema created once (fast)
  - No cross-loop asyncpg connections
  - Clean DB state after every test (rollback)
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.session import get_db, Base
from app.core.config import get_settings

settings = get_settings()

# Async URL (asyncpg) — used by per-test engines
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    settings.POSTGRES_DB, f"{settings.POSTGRES_DB}_test"
)
# Sync URL (psycopg2) — used by session-scoped schema fixture (no event loop)
TEST_DATABASE_URL_SYNC = settings.DATABASE_URL_SYNC.replace(
    settings.POSTGRES_DB, f"{settings.POSTGRES_DB}_test"
)


@pytest.fixture(scope="session")
def db_schema():
    """
    Create the test schema and all tables ONCE per session.

    Uses psycopg2 (sync) so there are NO event loop concerns.
    A sync session fixture can safely be session-scoped without
    conflicting with per-test async event loops.
    """
    engine = create_engine(TEST_DATABASE_URL_SYNC)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS secure"))
    Base.metadata.create_all(engine)
    engine.dispose()

    yield   # all tests run here

    # Teardown
    engine = create_engine(TEST_DATABASE_URL_SYNC)
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS secure CASCADE"))
    engine.dispose()


@pytest_asyncio.fixture
async def test_db(db_schema):
    """
    Fresh async engine + session for each test.

    Each call creates new asyncpg connections on the test's own event loop.
    Rolls back at teardown so the next test starts with a clean database.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_db):
    """
    Async HTTP test client with DB dependency overridden.

    override_get_db yields test_db WITHOUT committing, so all writes
    (test seed data + endpoint writes) stay in one transaction and are
    rolled back by test_db's teardown.
    """
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_redis():
    """
    Autouse — patches Redis for every test.

    is_token_blacklisted always returns False (token not revoked).
    Override locally to test revocation behaviour.
    """
    with patch(
        "app.core.security.is_token_blacklisted",
        new=AsyncMock(return_value=False),
    ):
        yield
