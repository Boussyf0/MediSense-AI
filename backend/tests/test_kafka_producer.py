"""
Unit tests for the Kafka IoT producer.

The real broker is never started — we only verify:
  - degraded mode (KAFKA_BROKERS empty) → publish_reading returns False, no I/O
  - configured mode → producer is built and send_and_wait is awaited
  - send failure → publish_reading swallows the exception and returns False
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_publish_reading_degraded_mode_returns_false(monkeypatch):
    """When KAFKA_BROKERS is empty the producer must be a no-op."""
    from app.services import kafka_producer
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "KAFKA_BROKERS", "")
    kafka_producer.reset_for_tests()

    sent = await kafka_producer.publish_reading(
        {"patient_uuid": "u", "hr": 70, "spo2": 98, "hrv": 40, "timestamp": 1}
    )
    assert sent is False


@pytest.mark.asyncio
async def test_publish_reading_sends_when_configured(monkeypatch):
    """With brokers set, the cached producer's send_and_wait is awaited."""
    from app.services import kafka_producer
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "KAFKA_BROKERS", "kafka:9092")
    kafka_producer.reset_for_tests()

    fake_producer = MagicMock()
    fake_producer.send_and_wait = AsyncMock()

    async def fake_get_producer():
        return fake_producer

    with patch.object(kafka_producer, "_get_producer", new=fake_get_producer):
        ok = await kafka_producer.publish_reading(
            {
                "patient_uuid": "u",
                "hr": 72,
                "spo2": 98,
                "hrv": 40,
                "timestamp": 1700000000,
            }
        )

    assert ok is True
    fake_producer.send_and_wait.assert_awaited_once()
    # Topic is the first positional arg
    args, _ = fake_producer.send_and_wait.call_args
    assert args[0] == "iot-vitals"


@pytest.mark.asyncio
async def test_publish_reading_handles_send_failure(monkeypatch):
    """Broker errors must not bubble — caller falls back to direct DB write."""
    from app.services import kafka_producer
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "KAFKA_BROKERS", "kafka:9092")
    kafka_producer.reset_for_tests()

    fake_producer = MagicMock()
    fake_producer.send_and_wait = AsyncMock(side_effect=RuntimeError("broker down"))

    async def fake_get_producer():
        return fake_producer

    with patch.object(kafka_producer, "_get_producer", new=fake_get_producer):
        ok = await kafka_producer.publish_reading(
            {"patient_uuid": "u", "hr": 72, "spo2": 98, "hrv": 40, "timestamp": 1}
        )

    assert ok is False


@pytest.mark.asyncio
async def test_publish_reading_aiokafka_missing_returns_false(monkeypatch):
    """If aiokafka isn't installed in the environment, publish must not crash."""
    from app.services import kafka_producer
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "KAFKA_BROKERS", "kafka:9092")
    kafka_producer.reset_for_tests()

    async def fake_get_producer():
        return None

    with patch.object(kafka_producer, "_get_producer", new=fake_get_producer):
        ok = await kafka_producer.publish_reading(
            {"patient_uuid": "u", "hr": 72, "spo2": 98, "hrv": 40, "timestamp": 1}
        )
    assert ok is False
