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
from datetime import datetime, timezone
from typing import Any

from app.api.v1.endpoints.metrics import prediction_latency_seconds
from app.services.lstm_anomaly_service import is_critical, score_window

logger = logging.getLogger(__name__)

WINDOW_5M_SECONDS  = 5  * 60    # 300 s
WINDOW_60M_SECONDS = 60 * 60    # 3 600 s
MIN_READINGS_FOR_SCORE = 5      # need at least 5 points before scoring


def _time_of_day_fr(hour: int) -> str:
    if 22 <= hour or hour < 6:
        return "pendant votre sommeil"
    if 6 <= hour < 12:
        return "ce matin"
    if 12 <= hour < 18:
        return "cet après-midi"
    return "ce soir"


def _activity_proxy(readings: list[dict]) -> str | None:
    """Cheap effort/repos classifier from HR spread in the 5m window.

    Mi Band samples HR every ~30s during workouts and every 1–5 min at rest,
    so range is a more reliable signal than count.
    """
    hrs = [r["hr"] for r in readings if r.get("hr") is not None]
    if len(hrs) < 3:
        return None
    spread = max(hrs) - min(hrs)
    mean = sum(hrs) / len(hrs)
    if spread >= 25 or mean >= 110:
        return "pendant un effort"
    if spread <= 8 and mean <= 80:
        return "au repos"
    return None


def build_anomaly_narrative(
    reading: dict,
    score_60m: float | None,
    window_readings: list[dict],
    now_ts: float | None = None,
) -> str:
    """Compose a one-sentence French narrative for an anomaly event.

    Deterministic template — no LLM call, no external I/O — so it stays
    cheap, testable, and works in degraded mode. Combines the triggering
    reading, severity bucket, time-of-day, and an activity proxy.
    """
    hr = reading.get("hr")
    spo2 = reading.get("spo2")
    hrv = reading.get("hrv")

    ts = datetime.fromtimestamp(now_ts or time.time(), tz=timezone.utc)
    when = _time_of_day_fr(ts.hour)
    activity = _activity_proxy(window_readings)

    headline: str
    if spo2 is not None and spo2 < 92:
        headline = f"Hypoxie : SpO₂ à {int(spo2)}%"
    elif hr is not None and hr >= 130:
        headline = f"Pic cardiaque à {int(hr)} bpm"
    elif hr is not None and hr <= 45:
        headline = f"Bradycardie à {int(hr)} bpm"
    elif hrv is not None and hrv <= 15:
        headline = f"Variabilité très basse ({int(hrv)} ms)"
    else:
        hr_part = f"{int(hr)} bpm" if hr is not None else "valeurs"
        headline = f"Signes vitaux atypiques ({hr_part})"

    context_bits: list[str] = [when]
    if activity:
        context_bits.append(activity)

    details: list[str] = []
    if spo2 is not None and spo2 >= 92:
        details.append(f"SpO₂ {int(spo2)}%")
    if hrv is not None and hrv > 15:
        details.append(f"variabilité {int(hrv)} ms")

    trend_tail = ""
    if score_60m is not None and score_60m >= 0.60:
        trend_tail = " La tendance reste élevée sur l'heure écoulée."

    sentence = f"{headline} détecté {' '.join(context_bits)}."
    if details:
        joined = ", ".join(details)
        sentence += f" {joined[0].upper()}{joined[1:]}."
    sentence += trend_tail
    return sentence


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

    if len(readings5) >= MIN_READINGS_FOR_SCORE:
        with prediction_latency_seconds.labels(model="lstm_anomaly").time():
            score_5m = score_window(readings5)
    else:
        score_5m = None
    if len(readings60) >= MIN_READINGS_FOR_SCORE:
        with prediction_latency_seconds.labels(model="bilstm_attn").time():
            score_60m = score_window(readings60)
    else:
        score_60m = None

    # Rule-based safety net — dangerous vitals alert immediately, regardless of the
    # LSTM score. Covers the cold-start window (before MIN_READINGS_FOR_SCORE) and a
    # missing/unavailable model (score_window returns 0.0 then).
    _hr = reading.get("hr")
    _spo2 = reading.get("spo2")
    rule_critical = (
        (_spo2 is not None and _spo2 < 90)
        or (_hr is not None and (_hr >= 130 or _hr <= 40))
    )
    lstm_critical = is_critical(score_5m) if score_5m is not None else False
    alert_critical = rule_critical or lstm_critical
    trend_elevated = (score_60m or 0) >= 0.60 if score_60m is not None else False

    # Always update Prometheus counters so Grafana panels react to traffic
    # even when no alert fires (severity=normal records the heartbeat).
    try:
        from app.api.v1.endpoints.metrics import iot_anomalies_detected_total
        if alert_critical:
            iot_anomalies_detected_total.labels(severity="critical", metric_type="lstm_5m").inc()
        if trend_elevated:
            iot_anomalies_detected_total.labels(severity="trend", metric_type="lstm_60m").inc()
    except Exception:
        logger.debug("Prometheus counter update failed", exc_info=True)

    narrative: str | None = None
    if alert_critical or trend_elevated:
        try:
            narrative = build_anomaly_narrative(
                reading=reading,
                score_60m=score_60m,
                window_readings=readings5,
                now_ts=now,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("narrative build failed: %s", exc)

    if alert_critical:
        logger.warning(
            "CRITICAL anomaly detected — patient=%s score_5m=%.3f narrative=%s",
            patient_uuid, score_5m, narrative,
        )
        # Push real-time alert to all connected clinicians (US-54).
        # Errors here must never break ingestion — wrap in try/except.
        try:
            from app.core.ws_manager import manager
            await manager.broadcast(
                "doctor",
                {
                    "type": "anomaly_critical",
                    "patient_uuid": patient_uuid,
                    "score_5m": score_5m,
                    "score_60m": score_60m,
                    "narrative": narrative,
                    "reading": {
                        "hr": reading.get("hr"),
                        "spo2": reading.get("spo2"),
                        "hrv": reading.get("hrv"),
                    },
                    "ts": now,
                },
            )
        except Exception as exc:
            logger.warning("WS broadcast failed: %s", exc)

        # Push FCM notification to the patient's registered devices (US-29).
        try:
            await _push_anomaly_to_patient(patient_uuid, score_5m, narrative)
        except Exception as exc:
            logger.warning("FCM push failed: %s", exc)

    return {
        "score_5m":       score_5m,
        "score_60m":      score_60m,
        "alert_critical": alert_critical,
        "trend_elevated": trend_elevated,
        "narrative":      narrative,
    }


async def _push_anomaly_to_patient(
    patient_uuid: str, score_5m: float | None, narrative: str | None = None
) -> None:
    """Best-effort FCM push to all device tokens registered by the patient.

    Patients share their UUID across the User and Patient tables, so
    `device_token.user_uuid == patient_uuid` for the affected user.
    """
    from sqlalchemy import select

    from app.db.models.device_token import DeviceToken
    from app.db.session import AsyncSessionLocal
    from app.services.fcm_service import send_to_tokens

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(DeviceToken.token).where(DeviceToken.user_uuid == patient_uuid)
            )
        ).scalars().all()
    if not rows:
        return
    score_str = f"{score_5m:.2f}" if score_5m is not None else "n/a"
    body = narrative or f"Anomaly score {score_str} — please open the app"
    await send_to_tokens(
        list(rows),
        title="Alerte vitaux",
        body=body,
        data={"type": "anomaly_critical", "patient_uuid": str(patient_uuid)},
    )


async def get_recent_scores(patient_uuid: str) -> dict[str, Any]:
    """Return the latest window scores for a patient (for the anomaly endpoint)."""
    try:
        redis = await _get_redis()
        raw5  = await redis.zrange(_key("5m",  patient_uuid), 0, -1)
        raw60 = await redis.zrange(_key("60m", patient_uuid), 0, -1)
        readings5  = [json.loads(r) for r in raw5]
        readings60 = [json.loads(r) for r in raw60]
    except Exception:
        logger.warning("Redis unavailable for anomaly scores", exc_info=True)
        readings5 = readings60 = []

    if len(readings5) >= MIN_READINGS_FOR_SCORE:
        with prediction_latency_seconds.labels(model="lstm_anomaly").time():
            score_5m = score_window(readings5)
    else:
        score_5m = None
    if len(readings60) >= MIN_READINGS_FOR_SCORE:
        with prediction_latency_seconds.labels(model="bilstm_attn").time():
            score_60m = score_window(readings60)
    else:
        score_60m = None

    alert_critical = is_critical(score_5m) if score_5m is not None else False
    trend_elevated = (score_60m or 0) >= 0.60 if score_60m is not None else False
    narrative: str | None = None
    if (alert_critical or trend_elevated) and readings5:
        try:
            narrative = build_anomaly_narrative(
                reading=readings5[-1],
                score_60m=score_60m,
                window_readings=readings5,
            )
        except Exception:  # pragma: no cover — defensive
            logger.warning("Narrative build failed", exc_info=True)
            narrative = None

    return {
        "patient_uuid":  patient_uuid,
        "score_5m":      score_5m,
        "score_60m":     score_60m,
        "readings_5m":   len(readings5),
        "readings_60m":  len(readings60),
        "alert_critical": alert_critical,
        "trend_elevated": trend_elevated,
        "narrative":     narrative,
    }
