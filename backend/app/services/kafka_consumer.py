"""
Kafka IoT consumer — Sprint 7 (US-25).

Consumes messages from the `iot-vitals` topic published by Samsung Watch BLE
gateway and persists them as BiometricReading rows.

Degraded mode: if KAFKA_BROKERS is empty or unreachable, incoming payloads are
buffered as newline-delimited JSON in KAFKA_BUFFER_DIR.  A background task
re-injects buffered rows every 30 s once the broker is reachable again.

Message schema (JSON):
  {
    "device_id":    "SAMSUNG-WATCH-ABC123",
    "patient_uuid": "<uuid>",
    "hr":           72,        # beats per minute
    "spo2":         98,        # percentage
    "hrv":          42,        # ms (RMSSD)
    "temperature":  36.6,      # °C  (unused in BiometricReading; stored in anomaly context)
    "timestamp":    1700000000 # Unix epoch seconds
  }
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.db.models.biometric_reading import BiometricReading
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()

_consumer_task: asyncio.Task | None = None  # singleton reference


async def _persist_reading(payload: dict) -> None:
    """Insert one BiometricReading row from a decoded Kafka message."""
    async with AsyncSessionLocal() as db:
        reading = BiometricReading(
            patient_uuid=uuid.UUID(payload["patient_uuid"]),
            ts=datetime.fromtimestamp(payload["timestamp"], tz=timezone.utc),
            hr=int(payload["hr"]),
            spo2=int(payload["spo2"]),
            hrv=int(payload["hrv"]),
        )
        db.add(reading)
        await db.flush()


async def _buffer_payload(payload: dict) -> None:
    """Write payload to the CSV/NDJSON buffer when Kafka is unavailable."""
    buf_dir = Path(settings.KAFKA_BUFFER_DIR)
    buf_dir.mkdir(parents=True, exist_ok=True)
    buf_file = buf_dir / "iot_buffer.ndjson"
    with buf_file.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload) + "\n")


async def _drain_buffer() -> None:
    """Re-inject buffered payloads once the broker is reachable."""
    buf_file = Path(settings.KAFKA_BUFFER_DIR) / "iot_buffer.ndjson"
    if not buf_file.exists():
        return
    lines = buf_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        return
    logger.info("Draining %d buffered IoT readings", len(lines))
    ok_lines: list[str] = []
    for line in lines:
        try:
            await _persist_reading(json.loads(line))
            ok_lines.append(line)
        except Exception as exc:
            logger.warning("Buffer drain failed for line: %s — %s", line[:80], exc)
    # Remove successfully replayed lines
    remaining = [l for l in lines if l not in ok_lines]
    buf_file.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")


async def _kafka_consumer_loop() -> None:  # pragma: no cover
    """Main consumer loop — tries aiokafka, falls back to degraded mode."""
    try:
        from aiokafka import AIOKafkaConsumer  # type: ignore[import]
        from aiokafka.errors import KafkaConnectionError  # type: ignore[import]
    except ImportError:
        logger.warning("aiokafka not installed — IoT consumer disabled")
        return

    if not settings.KAFKA_BROKERS:
        logger.info("KAFKA_BROKERS not set — IoT consumer in degraded mode (no-op)")
        return

    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_IOT,
        bootstrap_servers=settings.KAFKA_BROKERS,
        group_id="medisense-iot-consumer",
        auto_offset_reset="latest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )

    drain_counter = 0
    try:
        await consumer.start()
        logger.info("Kafka consumer started — topic=%s", settings.KAFKA_TOPIC_IOT)
        async for msg in consumer:
            try:
                await _persist_reading(msg.value)
            except Exception as exc:
                logger.error("Failed to persist IoT reading: %s", exc)
                await _buffer_payload(msg.value)

            drain_counter += 1
            if drain_counter % 300 == 0:  # drain every ~5 min at 1 msg/s
                await _drain_buffer()

    except (KafkaConnectionError, Exception) as exc:
        logger.warning("Kafka unavailable (%s) — consumer in degraded mode", exc)
    finally:
        try:
            await consumer.stop()
        except Exception:
            pass


async def start_kafka_consumer() -> None:  # pragma: no cover
    """Start the Kafka consumer as a background asyncio task (called from lifespan)."""
    global _consumer_task
    _consumer_task = asyncio.create_task(_kafka_consumer_loop())
    logger.info("IoT Kafka consumer task scheduled")


async def stop_kafka_consumer() -> None:  # pragma: no cover
    """Cancel the consumer task on shutdown."""
    global _consumer_task
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
