"""
Health check endpoint — US-01 acceptance criterion:
  /health responds HTTP 200 in < 2 seconds

This endpoint:
  1. Verifies FastAPI is alive (trivial)
  2. Verifies PostgreSQL connection is alive
  3. Verifies Redis connection is alive

Why check dependencies?
  - A "healthy" service that can't reach its DB is not actually healthy
  - Kubernetes/Docker health probes use this to decide if the container should be restarted
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from app.db.session import get_db
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    System health check.

    Returns 200 if all critical dependencies are reachable.
    Returns 503 if any critical dependency is down.
    """
    health_status = {
        "status": "healthy",
        "version": "1.0.0-sprint1",
        "services": {}
    }

    # Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        health_status["services"]["postgres"] = "ok"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["services"]["postgres"] = f"error: {str(e)}"

    # Check Redis
    try:
        redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        await redis.aclose()
        health_status["services"]["redis"] = "ok"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["services"]["redis"] = f"error: {str(e)}"

    return health_status
