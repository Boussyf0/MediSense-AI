"""
Unit tests for anomaly detection services.
- lstm_anomaly_service: score_window (no model), is_critical
- anomaly_detector: ingest_reading, get_recent_scores (with mocked Redis)
- kafka_consumer: _persist_reading, _buffer_payload, _drain_buffer
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    assert result["score_5m"] == pytest.approx(0.0, abs=1e-3)
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


@pytest.mark.asyncio
async def test_ingest_reading_critical_anomaly(test_db):
    """When a critical anomaly is scored, it broadcasts via WebSocket and attempts FCM push."""
    from app.services.anomaly_detector import ingest_reading
    from app.db.models.device_token import DeviceToken
    from app.db.models.user import User, UserRole

    patient_uuid = uuid.uuid4()
    readings = [{"hr": 140, "spo2": 85, "hrv": 12, "temperature": 38.5}] * 8
    # 5m window has 8 readings (< 10 -> score 0.95), 60m has 16 readings (>= 10 -> score 0.75)
    redis_mock = _make_redis_mock(readings_5m=readings, readings_60m=readings * 2)

    # Seed User first to avoid FK constraint error
    user = User(
        user_uuid=patient_uuid,
        email=f"patient-{patient_uuid}@example.com",
        hashed_password="mocked-hash",
        role=UserRole.PATIENT,
        first_name="Test",
        last_name="Patient",
        is_active=True
    )
    test_db.add(user)
    await test_db.flush()

    # Seed a DeviceToken to cover the FCM push lines
    test_db.add(DeviceToken(
        token="test-token-123",
        user_uuid=patient_uuid,
        platform="android",
    ))
    await test_db.flush()

    # Mock score_window to return 0.95 (critical) for 5m, and 0.75 for 60m
    def mock_score(window):
        return 0.95 if len(window) < 10 else 0.75

    mock_broadcast = AsyncMock(return_value=1)
    mock_send_to_tokens = AsyncMock()
    
    # Mock AsyncSessionLocal to yield the test_db session
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=test_db)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_local = MagicMock(return_value=ctx)

    with patch("app.services.anomaly_detector._get_redis", new_callable=AsyncMock, return_value=redis_mock), \
         patch("app.services.anomaly_detector.score_window", side_effect=mock_score), \
         patch("app.core.ws_manager.manager.broadcast", new=mock_broadcast), \
         patch("app.services.fcm_service.send_to_tokens", new=mock_send_to_tokens), \
         patch("app.db.session.AsyncSessionLocal", new=mock_session_local):
        
        result = await ingest_reading(str(patient_uuid), readings[0])

    assert result["score_5m"] == 0.95
    assert result["score_60m"] == 0.75
    assert result["alert_critical"] is True
    assert result["trend_elevated"] is True
    mock_broadcast.assert_called_once()
    mock_send_to_tokens.assert_called_once()


@pytest.mark.asyncio
async def test_get_recent_scores_with_enough_readings():
    """get_recent_scores returns scored windows when enough readings exist."""
    from app.services.anomaly_detector import get_recent_scores

    patient_uuid = str(uuid.uuid4())
    readings = [{"hr": 72, "spo2": 98, "hrv": 42, "temperature": 36.6}] * 8
    
    async def mock_zrange(key, start, end):
        if "60m" in key:
            return [json.dumps(r).encode() for r in readings] * 2  # 16 readings
        return [json.dumps(r).encode() for r in readings]  # 8 readings

    redis_mock = AsyncMock()
    redis_mock.zrange = mock_zrange

    def mock_score(window):
        return 0.95 if len(window) < 10 else 0.75

    with patch("app.services.anomaly_detector._get_redis", new_callable=AsyncMock, return_value=redis_mock), \
         patch("app.services.anomaly_detector.score_window", side_effect=mock_score):
        result = await get_recent_scores(patient_uuid)

    assert result["patient_uuid"] == patient_uuid
    assert result["score_5m"] == 0.95
    assert result["score_60m"] == 0.75
    assert result["alert_critical"] is True
    assert result["trend_elevated"] is True
    assert result["narrative"] is not None


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


def test_narrative_morning_bradycardia():
    """Bradycardia (HR ≤ 45) detected in the morning."""
    from app.services.anomaly_detector import build_anomaly_narrative

    reading = {"hr": 42, "spo2": 97, "hrv": 50}
    window = [{"hr": 42}, {"hr": 43}, {"hr": 41}, {"hr": 44}, {"hr": 42}]
    text = build_anomaly_narrative(
        reading=reading, score_60m=None, window_readings=window, now_ts=_ts_at(8),
    )
    assert "Bradycardie" in text
    assert "42 bpm" in text
    assert "matin" in text


def test_narrative_low_hrv():
    """Very low HRV (≤ 15ms) generates HRV-specific headline."""
    from app.services.anomaly_detector import build_anomaly_narrative

    reading = {"hr": 72, "spo2": 97, "hrv": 12}
    window = [{"hr": 71}, {"hr": 72}, {"hr": 73}]
    text = build_anomaly_narrative(
        reading=reading, score_60m=None, window_readings=window, now_ts=_ts_at(10),
    )
    assert "Variabilité" in text
    assert "12 ms" in text


def test_narrative_generic_headline():
    """When no specific pattern matches, generic headline is used."""
    from app.services.anomaly_detector import build_anomaly_narrative

    reading = {"hr": 95, "spo2": 96, "hrv": 25}
    window = [{"hr": 90}, {"hr": 95}, {"hr": 93}]
    text = build_anomaly_narrative(
        reading=reading, score_60m=None, window_readings=window, now_ts=_ts_at(15),
    )
    assert "atypiques" in text
    assert "après-midi" in text


def test_activity_proxy_too_few_readings():
    """Fewer than 3 HR readings → None (no classification)."""
    from app.services.anomaly_detector import _activity_proxy
    assert _activity_proxy([{"hr": 70}, {"hr": 72}]) is None


def test_activity_proxy_ambiguous():
    """Neither resting nor exercising → None."""
    from app.services.anomaly_detector import _activity_proxy
    readings = [{"hr": 85}, {"hr": 90}, {"hr": 95}, {"hr": 88}]
    assert _activity_proxy(readings) is None


def test_activity_proxy_resting():
    """Low spread, low mean → resting."""
    from app.services.anomaly_detector import _activity_proxy
    readings = [{"hr": 62}, {"hr": 64}, {"hr": 63}, {"hr": 65}, {"hr": 63}]
    assert _activity_proxy(readings) == "au repos"


def test_time_of_day_fr_afternoon():
    """Hour 15 → 'cet après-midi'."""
    from app.services.anomaly_detector import _time_of_day_fr
    assert _time_of_day_fr(15) == "cet après-midi"


def test_time_of_day_fr_morning():
    """Hour 8 → 'ce matin'."""
    from app.services.anomaly_detector import _time_of_day_fr
    assert _time_of_day_fr(8) == "ce matin"


# ── kafka_consumer ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_persist_reading_inserts_row(test_db):
    """_persist_reading should insert a BiometricReading row via the test DB session."""
    import uuid as _uuid
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


@pytest.mark.asyncio
async def test_kafka_consumer_loop_calls_ingest_reading():
    """Test that _kafka_consumer_loop calls ingest_reading upon receiving a message."""
    import sys
    from app.services.kafka_consumer import _kafka_consumer_loop
    from app.core.config import get_settings
    
    settings = get_settings()
    
    class MockMsg:
        def __init__(self, value):
            self.value = value

    class MockConsumerIter:
        def __init__(self, msgs):
            self.msgs = msgs
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.msgs:
                raise StopAsyncIteration
            return self.msgs.pop(0)

    patient_uuid = str(uuid.uuid4())
    payload = {
        "device_id": "SAMSUNG-WATCH-ABC123",
        "patient_uuid": patient_uuid,
        "hr": 75, "spo2": 98, "hrv": 45,
        "temperature": 36.6,
        "timestamp": 1700000000
    }
    
    mock_consumer = MagicMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.assignment = MagicMock(return_value=[])
    mock_consumer.end_offsets = AsyncMock(return_value={})
    mock_consumer.__aiter__ = MagicMock(return_value=MockConsumerIter([MockMsg(payload)]))
    
    mock_consumer_cls = MagicMock(return_value=mock_consumer)
    
    mock_persist = AsyncMock()
    mock_ingest = AsyncMock()

    # Save original modules
    orig_aiokafka = sys.modules.get("aiokafka")
    orig_aiokafka_errors = sys.modules.get("aiokafka.errors")
    
    # Mock modules
    mock_aiokafka = MagicMock()
    mock_aiokafka.AIOKafkaConsumer = mock_consumer_cls
    mock_aiokafka_errors = MagicMock()
    mock_aiokafka_errors.KafkaConnectionError = Exception
    
    sys.modules["aiokafka"] = mock_aiokafka
    sys.modules["aiokafka.errors"] = mock_aiokafka_errors

    try:
        with patch.object(settings, "KAFKA_BROKERS", "localhost:9092"), \
             patch("app.services.kafka_consumer.settings", settings), \
             patch("app.services.kafka_consumer._persist_reading", new=mock_persist), \
             patch("app.services.anomaly_detector.ingest_reading", new=mock_ingest):
            
            await _kafka_consumer_loop()
    finally:
        # Restore original modules
        if orig_aiokafka is None:
            sys.modules.pop("aiokafka", None)
        else:
            sys.modules["aiokafka"] = orig_aiokafka
            
        if orig_aiokafka_errors is None:
            sys.modules.pop("aiokafka.errors", None)
        else:
            sys.modules["aiokafka.errors"] = orig_aiokafka_errors
        
    mock_persist.assert_called_once_with(payload)
    mock_ingest.assert_called_once_with(patient_uuid, payload)


@pytest.mark.asyncio
async def test_kafka_consumer_loop_buffers_on_error(tmp_path):
    """Test that _kafka_consumer_loop buffers payloads if persist or ingest throws an error."""
    import sys
    from app.services.kafka_consumer import _kafka_consumer_loop
    from app.core.config import get_settings
    
    settings = get_settings()
    buf_dir = tmp_path / "kafka-buffer"
    
    class MockMsg:
        def __init__(self, value):
            self.value = value

    class MockConsumerIter:
        def __init__(self, msgs):
            self.msgs = msgs
        def __aiter__(self):
            return self
        async def __anext__(self):
            if not self.msgs:
                raise StopAsyncIteration
            return self.msgs.pop(0)

    patient_uuid = str(uuid.uuid4())
    payload = {
        "device_id": "SAMSUNG-WATCH-ABC123",
        "patient_uuid": patient_uuid,
        "hr": 75, "spo2": 98, "hrv": 45,
        "temperature": 36.6,
        "timestamp": 1700000000
    }
    
    mock_consumer = MagicMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.assignment = MagicMock(return_value=[])
    mock_consumer.end_offsets = AsyncMock(return_value={})
    mock_consumer.__aiter__ = MagicMock(return_value=MockConsumerIter([MockMsg(payload)]))
    
    mock_consumer_cls = MagicMock(return_value=mock_consumer)
    
    mock_persist = AsyncMock(side_effect=ValueError("DB insertion error"))

    # Save original modules
    orig_aiokafka = sys.modules.get("aiokafka")
    orig_aiokafka_errors = sys.modules.get("aiokafka.errors")
    
    # Mock modules
    mock_aiokafka = MagicMock()
    mock_aiokafka.AIOKafkaConsumer = mock_consumer_cls
    mock_aiokafka_errors = MagicMock()
    mock_aiokafka_errors.KafkaConnectionError = Exception
    
    sys.modules["aiokafka"] = mock_aiokafka
    sys.modules["aiokafka.errors"] = mock_aiokafka_errors
    
    try:
        with patch.object(settings, "KAFKA_BROKERS", "localhost:9092"), \
             patch.object(settings, "KAFKA_BUFFER_DIR", str(buf_dir)), \
             patch("app.services.kafka_consumer.settings", settings), \
             patch("app.services.kafka_consumer._persist_reading", new=mock_persist):
            
            await _kafka_consumer_loop()
    finally:
        # Restore original modules
        if orig_aiokafka is None:
            sys.modules.pop("aiokafka", None)
        else:
            sys.modules["aiokafka"] = orig_aiokafka
            
        if orig_aiokafka_errors is None:
            sys.modules.pop("aiokafka.errors", None)
        else:
            sys.modules["aiokafka.errors"] = orig_aiokafka_errors
        
    mock_persist.assert_called_once_with(payload)
    lines = (buf_dir / "iot_buffer.ndjson").read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["patient_uuid"] == patient_uuid
