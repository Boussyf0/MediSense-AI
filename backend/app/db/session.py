"""
Async database session management.

Why async SQLAlchemy?
  - FastAPI is async-first. Using sync SQLAlchemy would block the event loop
    during DB queries, killing concurrency. With asyncpg, DB I/O is truly non-blocking.

Connection pool settings explained:
  - pool_size=10: max persistent connections kept alive
  - max_overflow=20: extra connections allowed beyond pool_size under load
  - pool_timeout=30: how long to wait for a free connection before raising
  - pool_recycle=1800: recycle connections every 30min (prevents stale connections)
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    echo=(settings.APP_ENV == "development"),   # log SQL queries in dev only
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # don't expire objects after commit (prevents lazy load errors)
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


async def get_db() -> AsyncSession:
    """
    FastAPI dependency — yields an async DB session per request.

    Usage in endpoints:
        @router.get("/something")
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            ...

    The session is automatically closed after the request, even on exceptions.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
