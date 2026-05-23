"""
IoT Simulator Worker — Sprint 7.

Publishes synthetic biometric readings to the Kafka topic consumed by
`backend/app/services/kafka_consumer.py`. Replaces the missing Samsung
Watch BLE gateway in dev / demo environments.

Configuration (env vars):
  KAFKA_BROKERS        e.g. "kafka:9092"            (required)
  KAFKA_TOPIC_IOT      default "iot-vitals"
  SIM_PATIENT_UUIDS    comma-separated UUIDs        (required for production)
  SIM_RATE_HZ          messages per second per patient (default 10)
  SIM_ANOMALY_RATIO    fraction of windows containing an anomaly (default 0.05)

Exit codes:
  0  graceful shutdown (SIGTERM)
  1  configuration error
"""
import asyncio
import json
import logging
import os
import random
import signal
import sys
import time
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("iot-simulator")


def _load_patients() -> list[str]:
    raw = os.getenv("SIM_PATIENT_UUIDS", "").strip()
    if not raw:
        # Generate a small demo cohort so the simulator runs out of the box
        return [str(uuid.uuid4()) for _ in range(3)]
    return [p.strip() for p in raw.split(",") if p.strip()]


def _make_reading(patient_uuid: str, anomalous: bool) -> dict:
    if anomalous:
        hr = random.randint(105, 130)
        spo2 = random.randint(85, 91)
        hrv = random.randint(10, 20)
    else:
        hr = random.randint(60, 90)
        spo2 = random.randint(96, 99)
        hrv = random.randint(35, 60)
    return {
        "device_id": f"SIM-{patient_uuid[:8]}",
        "patient_uuid": patient_uuid,
        "hr": hr,
        "spo2": spo2,
        "hrv": hrv,
        "temperature": round(36.4 + random.random() * 0.6, 1),
        "timestamp": int(time.time()),
    }


async def run() -> None:
    brokers = os.getenv("KAFKA_BROKERS")
    if not brokers:
        log.error("KAFKA_BROKERS not set — simulator cannot start")
        sys.exit(1)

    topic = os.getenv("KAFKA_TOPIC_IOT", "iot-vitals")
    rate_hz = float(os.getenv("SIM_RATE_HZ", "10"))
    anomaly_ratio = float(os.getenv("SIM_ANOMALY_RATIO", "0.05"))
    patients = _load_patients()
    interval = 1.0 / rate_hz if rate_hz > 0 else 0.1

    log.info(
        "Starting simulator: brokers=%s topic=%s patients=%d rate_hz=%.1f anomaly=%.2f",
        brokers, topic, len(patients), rate_hz, anomaly_ratio,
    )

    try:
        from aiokafka import AIOKafkaProducer
    except ImportError as exc:
        log.error("aiokafka not installed: %s", exc)
        sys.exit(1)

    producer = AIOKafkaProducer(
        bootstrap_servers=brokers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    await producer.start()
    log.info("Kafka producer connected")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    sent = 0
    try:
        while not stop_event.is_set():
            patient = random.choice(patients)
            anomalous = random.random() < anomaly_ratio
            payload = _make_reading(patient, anomalous)
            await producer.send_and_wait(topic, payload)
            sent += 1
            if sent % 100 == 0:
                log.info("sent %d messages", sent)
            await asyncio.sleep(interval)
    finally:
        await producer.stop()
        log.info("Producer stopped after %d messages", sent)


if __name__ == "__main__":
    asyncio.run(run())
