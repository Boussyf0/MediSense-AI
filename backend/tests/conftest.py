"""
Pytest fixtures — shared across all test files.

Why a test database?
  - Tests must NEVER touch the production/development database
  - We use a separate test DB that is created/dropped per test session
  - SQLite in-memory would be simpler but doesn't support pgcrypto/UUID
    → we use a real PostgreSQL test DB
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from unittest.mock import AsyncMock, patch

from app.main import app
from app.db.session import get_db, Base
from app.core.config import get_settings

settings = get_settings()

# Override DB URL for tests (uses same postgres but different DB name)
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    settings.POSTGRES_DB, f"{settings.POSTGRES_DB}_test"
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine — shared across the entire test session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_db(test_engine):
    """Provide a test DB session that rolls back after each test."""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_db):
    """
    Async test client with DB dependency overridden.

    Why override dependencies?
      - FastAPI's dependency injection allows swapping get_db() for tests
      - The test client uses the test DB, not the real one
    """
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
