"""
Anomaly Detector — Sprint 7 (US-28).

Implements two sliding windows over Redis sorted sets:
  - 5-minute critical window: score via LSTM → immediate WebSocket alert if critical
  - 60-minute trend window: aggregate score → trigger DPA summary if trending high

Redis key patterns:
  iot:window:5m:{patient_uuid}   — sorted set, score=timestamp (epoch), value=JSON reading
  iot:window:60m:{patient_uuid}  — sorted set, same schema
"""
import json
import logging
import time
from typing import Any

from app.services.lstm_anomaly_service import is_critical, score_window

logger = logging.getLogger(__name__)

WINDOW_5M_SECONDS  = 5  * 60    # 300 s
WINDOW_60M_SECONDS = 60 * 60    # 3 600 s
MIN_READINGS_FOR_SCORE = 5      # need at least 5 points before scoring


async def _get_redis():
    import redis.asyncio as aioredis
    from app.core.config import get_settings
    return await aioredis.from_url(
        get_settings().REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


def _key(window: str, patient_uuid: str) -> str:
    return f"iot:window:{window}:{patient_uuid}"


async def ingest_reading(patient_uuid: str, reading: dict) -> dict[str, Any]:
    """
    Add a biometric reading to both sliding windows and score if enough data.

    Returns:
        {
            "score_5m": float | None,
            "score_60m": float | None,
            "alert_critical": bool,
            "trend_elevated": bool,
        }
    """
    now = time.time()
    encoded = json.dumps(reading)

    try:
        redis = await _get_redis()

        key5  = _key("5m",  patient_uuid)
        key60 = _key("60m", patient_uuid)

        pipe = redis.pipeline()
        pipe.zadd(key5,  {encoded: now})
        pipe.zadd(key60, {encoded: now})
        # Trim to window bounds
        pipe.zremrangebyscore(key5,  "-inf", now - WINDOW_5M_SECONDS)
        pipe.zremrangebyscore(key60, "-inf", now - WINDOW_60M_SECONDS)
        pipe.zrange(key5,  0, -1)
        pipe.zrange(key60, 0, -1)
        results = await pipe.execute()

        raw5  = results[4]
        raw60 = results[5]

        readings5  = [json.loads(r) for r in raw5]
        readings60 = [json.loads(r) for r in raw60]

    except Exception as exc:
        logger.warning("Redis unavailable — using in-memory fallback: %s", exc)
        readings5 = readings60 = [reading]

    score_5m  = score_window(readings5)  if len(readings5)  >= MIN_READINGS_FOR_SCORE else None
    score_60m = score_window(readings60) if len(readings60) >= MIN_READINGS_FOR_SCORE else None

    alert_critical = is_critical(score_5m)  if score_5m  is not None else False
    trend_elevated = (score_60m or 0) >= 0.60 if score_60m is not None else False

    if alert_critical:
        logger.warning(
            "CRITICAL anomaly detected — patient=%s score_5m=%.3f",
            patient_uuid, score_5m,
        )

    return {
        "score_5m":       score_5m,
        "score_60m":      score_60m,
        "alert_critical": alert_critical,
        "trend_elevated": trend_elevated,
    }


async def get_recent_scores(patient_uuid: str) -> dict[str, Any]:
    """Return the latest window scores for a patient (for the anomaly endpoint)."""
    try:
        redis = await _get_redis()
        raw5  = await redis.zrange(_key("5m",  patient_uuid), 0, -1)
        raw60 = await redis.zrange(_key("60m", patient_uuid), 0, -1)
        readings5  = [json.loads(r) for r in raw5]
        readings60 = [json.loads(r) for r in raw60]
    except Exception:
        readings5 = readings60 = []

    score_5m  = score_window(readings5)  if len(readings5)  >= MIN_READINGS_FOR_SCORE else None
    score_60m = score_window(readings60) if len(readings60) >= MIN_READINGS_FOR_SCORE else None

    return {
        "patient_uuid":  patient_uuid,
        "score_5m":      score_5m,
        "score_60m":     score_60m,
        "readings_5m":   len(readings5),
        "readings_60m":  len(readings60),
        "alert_critical": is_critical(score_5m) if score_5m is not None else False,
        "trend_elevated": (score_60m or 0) >= 0.60 if score_60m is not None else False,
    }
