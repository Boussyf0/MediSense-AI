"""
Unit tests for anomaly detection services.
- lstm_anomaly_service: score_window (no model), is_critical
- anomaly_detector: ingest_reading, get_recent_scores (with mocked Redis)
- kafka_consumer: _persist_reading, _buffer_payload, _drain_buffer
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.biometric_reading import BiometricReading
from app.db.models.patient import Patient


# ── lstm_anomaly_service ──────────────────────────────────────────────────

def test_score_window_no_model_returns_zero(monkeypatch):
    """When no .pt model file exists, score_window must return 0.0 gracefully."""
    from app.services import lstm_anomaly_service
    from app.core.config import get_settings

    # Reset module cache and point LSTM_MODEL_PATH at a non-existent file.
    monkeypatch.setattr(lstm_anomaly_service, "_model", None)
    monkeypatch.setattr(lstm_anomaly_service, "_device", None)
    monkeypatch.setattr(get_settings(), "LSTM_MODEL_PATH", "models/_does_not_exist.pt")

    vitals = [{"hr": 72, "spo2": 98, "hrv": 42, "temperature": 36.6}] * 10
    assert lstm_anomaly_service.score_window(vitals) == 0.0


def test_score_window_empty_vitals_returns_zero(monkeypatch):
    """Empty vitals list should fail safely → 0.0 (no crash)."""
    from app.services import lstm_anomaly_service
    from app.core.config import get_settings

    monkeypatch.setattr(lstm_anomaly_service, "_model", None)
    monkeypatch.setattr(lstm_anomaly_service, "_device", None)
    monkeypatch.setattr(get_settings(), "LSTM_MODEL_PATH", "models/_does_not_exist.pt")

    assert lstm_anomaly_service.score_window([]) == 0.0


def test_is_critical_above_threshold():
    from app.services.lstm_anomaly_service import is_critical
    assert is_critical(0.95) is True


def test_is_critical_below_threshold():
    from app.services.lstm_anomaly_service import is_critical
    assert is_critical(0.10) is False


def test_is_critical_at_boundary():
    from app.services.lstm_anomaly_service import is_critical
    # Default threshold is 0.80; exactly at threshold should be True
    assert is_critical(0.80) is True


# ── anomaly_detector ──────────────────────────────────────────────────────

def _make_redis_mock(readings_5m: list, readings_60m: list) -> AsyncMock:
    """Build a mock Redis pipeline result matching the detector's expected structure."""
    pipeline_mock = AsyncMock()
    pipeline_mock.execute = AsyncMock(return_value=[
        None, None, None, None,
        [json.dumps(r).encode() for r in readings_5m],
        [json.dumps(r).encode() for r in readings_60m],
    ])
    pipeline_mock.zadd = MagicMock()
    pipeline_mock.zremrangebyscore = MagicMock()
    pipeline_mock.zrange = MagicMock()

    redis_mock = AsyncMock()
    redis_mock.pipeline = MagicMock(return_value=pipeline_mock)
    redis_mock.zrange = AsyncMock(return_value=[])
    return redis_mock


@pytest.mark.asyncio
async def test_ingest_reading_no_redis_fallback():
    """When Redis is unavailable, ingest_reading returns scores without crashing."""
    from app.services.anomaly_detector import ingest_reading

    with patch(
        "app.services.anomaly_detector._get_redis",
        new_callable=AsyncMock,
        side_effect=ConnectionRefusedError("Redis unavailable"),
    ):
        result = await ingest_reading(str(uuid.uuid4()), {"hr": 72, "spo2": 98, "hrv": 42, "temperature": 36.6})

    assert "score_5m" in result
    assert "alert_critical" in result
    assert result["alert_critical"] is False


@pytest.mark.asyncio
async def test_ingest_reading_with_mock_redis_few_readings():
    """With < MIN_READINGS_FOR_SCORE points, scores should be None."""
    from app.services.anomaly_detector import ingest_reading

    # Only 3 readings — below MIN_READINGS_FOR_SCORE=5
    readings = [{"hr": 72, "spo2": 98, "hrv": 42, "temperature": 36.6}] * 3
    redis_mock = _make_redis_mock(readings_5m=readings, readings_60m=readings)

    with patch("app.services.anomaly_detector._get_redis", new_callable=AsyncMock, return_value=redis_mock):
        result = await ingest_reading(str(uuid.uuid4()), readings[0])

    assert result["score_5m"] is None
    assert result["score_60m"] is None
    assert result["alert_critical"] is False
    assert result["trend_elevated"] is False


@pytest.mark.asyncio
async def test_ingest_reading_with_enough_readings():
    """With >= 5 readings, score_window is called (returns 0.0 when no model)."""
    from app.services.anomaly_detector import ingest_reading

    readings = [{"hr": 72, "spo2": 98, "hrv": 42, "temperature": 36.6}] * 8
    redis_mock = _make_redis_mock(readings_5m=readings, readings_60m=readings)

    with patch("app.services.anomaly_detector._get_redis", new_callable=AsyncMock, return_value=redis_mock):
        result = await ingest_reading(str(uuid.uuid4()), readings[0])

    # score_window returns 0.0 when no model → not critical
    assert result["score_5m"] == pytest.approx(0.0)
    assert result["alert_critical"] is False


@pytest.mark.asyncio
async def test_get_recent_scores_no_redis():
    """When Redis is unavailable, get_recent_scores returns empty scores."""
    from app.services.anomaly_detector import get_recent_scores

    patient_uuid = str(uuid.uuid4())
    with patch(
        "app.services.anomaly_detector._get_redis",
        new_callable=AsyncMock,
        side_effect=ConnectionRefusedError("Redis unavailable"),
    ):
        result = await get_recent_scores(patient_uuid)

    assert result["patient_uuid"] == patient_uuid
    assert result["score_5m"] is None
    assert result["score_60m"] is None
    assert result["readings_5m"] == 0
    assert result["readings_60m"] == 0
    assert result["alert_critical"] is False


@pytest.mark.asyncio
async def test_get_recent_scores_with_redis():
    """get_recent_scores returns correct structure with mocked Redis."""
    from app.services.anomaly_detector import get_recent_scores

    patient_uuid = str(uuid.uuid4())
    redis_mock = AsyncMock()
    redis_mock.zrange = AsyncMock(return_value=[])  # empty windows

    with patch("app.services.anomaly_detector._get_redis", new_callable=AsyncMock, return_value=redis_mock):
        result = await get_recent_scores(patient_uuid)

    assert result["patient_uuid"] == patient_uuid
    assert result["score_5m"] is None
    assert result["readings_5m"] == 0


# ── narrative builder ─────────────────────────────────────────────────────

def _ts_at(hour: int) -> float:
    """Build a UTC epoch timestamp at the given hour-of-day for narrative tests."""
    return datetime(2026, 5, 20, hour, 30, tzinfo=timezone.utc).timestamp()


def test_narrative_hr_spike_evening_effort():
    from app.services.anomaly_detector import build_anomaly_narrative

    reading = {"hr": 142, "spo2": 96, "hrv": 38}
    # 5m window with wide HR spread → effort proxy fires
    window = [
        {"hr": 95}, {"hr": 110}, {"hr": 125}, {"hr": 138}, {"hr": 142},
    ]
    text = build_anomaly_narrative(
        reading=reading, score_60m=0.4, window_readings=window, now_ts=_ts_at(20),
    )
    assert "142 bpm" in text
    assert "ce soir" in text
    assert "effort" in text
    assert "SpO₂ 96%" in text


def test_narrative_hypoxia_sleep_window():
    from app.services.anomaly_detector import build_anomaly_narrative

    reading = {"hr": 60, "spo2": 88, "hrv": 35}
    window = [{"hr": 58}, {"hr": 60}, {"hr": 61}, {"hr": 59}, {"hr": 60}]
    text = build_anomaly_narrative(
        reading=reading, score_60m=0.2, window_readings=window, now_ts=_ts_at(3),
    )
    assert "Hypoxie" in text
    assert "88%" in text
    assert "sommeil" in text


def test_narrative_trend_tail_when_60m_elevated():
    from app.services.anomaly_detector import build_anomaly_narrative

    reading = {"hr": 135, "spo2": 97, "hrv": 30}
    window = [{"hr": 132}, {"hr": 135}, {"hr": 136}, {"hr": 138}, {"hr": 135}]
    text = build_anomaly_narrative(
        reading=reading, score_60m=0.75, window_readings=window, now_ts=_ts_at(14),
    )
    assert "tendance" in text.lower() or "heure" in text.lower()


# ── kafka_consumer ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_persist_reading_inserts_row(test_db):
    """_persist_reading should insert a BiometricReading row via the test DB session."""
    import uuid as _uuid
    from app.db.models.patient import Patient
    from app.services.kafka_consumer import _persist_reading

    patient_uuid = _uuid.uuid4()
    test_db.add(Patient(
        patient_uuid=patient_uuid,
        consent_iot=True,
        consent_nlp=False,
        consent_sharing=False,
        sms_opt_out=False,
        birth_year=1990,
        sex="M",
        city_code="40000",
        chronic_conditions=[],
    ))
    await test_db.flush()

    payload = {
        "patient_uuid": str(patient_uuid),
        "hr": 75, "spo2": 97, "hrv": 38,
        "temperature": 36.8,
        "timestamp": 1700000000,
    }

    with patch("app.services.kafka_consumer.AsyncSessionLocal") as mock_factory:
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=test_db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = ctx

        await _persist_reading(payload)

    # flush ensures insert ran without exception
    await test_db.flush()


@pytest.mark.asyncio
async def test_buffer_payload_writes_ndjson(tmp_path):
    """_buffer_payload should append a JSON line to the buffer file."""
    from app.services.kafka_consumer import _buffer_payload
    from app.core.config import get_settings

    settings = get_settings()
    buf_dir = tmp_path / "kafka-buffer"

    with patch.object(settings, "KAFKA_BUFFER_DIR", str(buf_dir)):
        with patch("app.services.kafka_consumer.settings", settings):
            payload = {"patient_uuid": str(uuid.uuid4()), "hr": 70, "spo2": 98}
            await _buffer_payload(payload)
            await _buffer_payload(payload)

    lines = (buf_dir / "iot_buffer.ndjson").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["hr"] == 70


@pytest.mark.asyncio
async def test_drain_buffer_empty_file_noop(tmp_path):
    """_drain_buffer on a missing file should not raise."""
    from app.services.kafka_consumer import _drain_buffer
    from app.core.config import get_settings

    settings = get_settings()
    with patch.object(settings, "KAFKA_BUFFER_DIR", str(tmp_path / "nonexistent")):
        with patch("app.services.kafka_consumer.settings", settings):
            await _drain_buffer()  # should not raise
