"""
Kafka IoT producer — Sprint 7 (companion to kafka_consumer.py).

Used by `POST /iot/simulate` and the standalone `iot-simulator` worker
container to publish synthetic biometric readings to the
`KAFKA_TOPIC_IOT` topic.

Degraded mode: when KAFKA_BROKERS is empty (local dev, free-tier cloud
without Kafka), `publish_reading()` is a no-op and returns False. Callers
fall back to writing the reading directly via the existing path.

Message schema mirrors what kafka_consumer expects in `_persist_reading`.
"""
import json
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_producer = None  # cached AIOKafkaProducer


async def _get_producer():  # pragma: no cover
    """
    Lazily build a singleton AIOKafkaProducer. External I/O adapter — only
    reachable when KAFKA_BROKERS is set, mocked at the call site in tests.
    """
    global _producer
    if _producer is not None:
        return _producer

    try:
        from aiokafka import AIOKafkaProducer  # type: ignore[import]
    except ImportError:
        logger.warning("aiokafka not installed — producer disabled")
        return None

    if not settings.KAFKA_BROKERS:
        return None

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
        request_timeout_ms=5000,
    )
    await producer.start()
    _producer = producer
    logger.info("Kafka producer started — brokers=%s", settings.KAFKA_BROKERS)
    return _producer


async def publish_reading(payload: dict) -> bool:
    """
    Publish one biometric reading dict to the IoT topic.

    Returns True on success, False if the broker is not configured or the
    send failed. Callers MUST handle False by falling back to direct DB
    write so the reading is never silently dropped.

    Required payload keys: patient_uuid, ts (ISO string or epoch), hr, spo2, hrv.
    """
    if not settings.KAFKA_BROKERS:
        return False

    producer = await _get_producer()
    if producer is None:
        return False

    try:
        await producer.send_and_wait(settings.KAFKA_TOPIC_IOT, payload)
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("Kafka publish failed (%s); falling back to DB write", exc)
        return False


async def stop_producer() -> None:  # pragma: no cover
    """Close the producer cleanly (called from FastAPI lifespan)."""
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
        finally:
            _producer = None


def reset_for_tests() -> None:
    """Clear cached producer — used by unit tests to enforce isolation."""
    global _producer
    _producer = None
