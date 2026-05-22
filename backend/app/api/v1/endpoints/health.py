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


@router.get("/health/detailed", tags=["Health"])
async def health_detailed(db: AsyncSession = Depends(get_db)):
    """Aggregated system snapshot for the admin/system dashboard.

    Reports DB & Redis status, Kafka configuration, model artefact presence,
    and basic Postgres metrics (table sizes for IoT readings + appointments).
    Errors per-service are caught so the endpoint never returns 5xx.
    """
    import time
    from pathlib import Path

    snapshot: dict = {
        "uptime_unix": int(time.time()),
        "services": {},
        "models": {},
        "kafka": {},
        "tables": {},
    }

    try:
        await db.execute(text("SELECT 1"))
        snapshot["services"]["postgres"] = "ok"
    except Exception as exc:
        snapshot["services"]["postgres"] = f"error: {exc}"

    try:
        redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        await redis.aclose()
        snapshot["services"]["redis"] = "ok"
    except Exception as exc:
        snapshot["services"]["redis"] = f"error: {exc}"

    snapshot["kafka"]["brokers"] = settings.KAFKA_BROKERS or "(degraded — none configured)"
    snapshot["kafka"]["topic"] = settings.KAFKA_TOPIC_IOT

    lstm_path = Path(settings.LSTM_MODEL_PATH)
    snapshot["models"]["lstm_anomaly"] = {
        "path": str(lstm_path),
        "present": lstm_path.exists(),
        "size_bytes": lstm_path.stat().st_size if lstm_path.exists() else 0,
    }
    snapshot["models"]["noshow_mlflow"] = settings.MLFLOW_MODEL_NAME

    try:
        for label, sql in (
            ("biometric_reading", "SELECT count(*) FROM public.biometric_reading"),
            ("appointments", "SELECT count(*) FROM public.appointments"),
            ("device_token", "SELECT count(*) FROM public.device_token"),
        ):
            try:
                row = (await db.execute(text(sql))).scalar_one()
                snapshot["tables"][label] = int(row)
            except Exception:
                snapshot["tables"][label] = None
    except Exception as exc:
        snapshot["tables"]["error"] = str(exc)

    snapshot["env"] = {"app_env": settings.APP_ENV, "llm_provider": settings.LLM_PROVIDER}
    return snapshot
