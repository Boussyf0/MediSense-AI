import math
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_patient
from app.db.models.biometric_reading import BiometricReading
from app.db.models.iot_device import IotDevice
from app.db.models.patient import Patient
from app.db.session import get_db
from app.schemas.iot import DeviceStatus, IngestBatch, IngestResponse, VitalPoint
from app.services.kafka_producer import publish_reading

router = APIRouter(prefix="/iot", tags=["IoT"])


_RANGE_RE = re.compile(r"^(\d+)([dh])$")


def _parse_range(range_str: str) -> timedelta:
    m = _RANGE_RE.match(range_str.strip().lower())
    if not m:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid range. Use formats like '7d' or '24h'.",
        )
    n = int(m.group(1))
    unit = m.group(2)
    if n <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Range must be a positive integer.",
        )
    return timedelta(days=n) if unit == "d" else timedelta(hours=n)


@router.get("/vitals", response_model=list[VitalPoint])
async def get_vitals(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
    range: str = Query(default="7d"),
) -> list[VitalPoint]:
    delta = _parse_range(range)
    patient_uuid = uuid.UUID(current_user.sub)
    cutoff = datetime.now(timezone.utc) - delta

    result = await db.execute(
        select(BiometricReading)
        .where(
            BiometricReading.patient_uuid == patient_uuid,
            BiometricReading.ts >= cutoff,
        )
        .order_by(BiometricReading.ts.asc())
    )
    readings = result.scalars().all()
    return [VitalPoint.model_validate(r) for r in readings]


@router.get("/devices", response_model=DeviceStatus)
async def get_device(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> DeviceStatus:
    patient_uuid = uuid.UUID(current_user.sub)
    result = await db.execute(
        select(IotDevice).where(IotDevice.patient_uuid == patient_uuid)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceStatus.model_validate(device)


@router.post("/simulate", response_model=DeviceStatus)
async def simulate_device(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> DeviceStatus:
    """
    Register a virtual device and seed 7 days of realistic biometric readings.

    Designed for demo and development environments where no physical bracelet
    is available. Calling this endpoint twice is idempotent — the device is
    upserted and previous readings are replaced.
    """
    patient_uuid = uuid.UUID(current_user.sub)

    # Guard: Patient record must exist (booking and FK constraints require it)
    patient = (
        await db.execute(select(Patient).where(Patient.patient_uuid == patient_uuid))
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient record not found — contact your administrator.",
        )

    now = datetime.now(timezone.utc)

    # Upsert IotDevice
    device = (
        await db.execute(select(IotDevice).where(IotDevice.patient_uuid == patient_uuid))
    ).scalar_one_or_none()
    if device is None:
        device = IotDevice(patient_uuid=patient_uuid, paired=True, last_sync=now, battery=85)
        db.add(device)
    else:
        device.paired = True
        device.last_sync = now
        device.battery = 85

    # Replace existing readings (clean slate on re-simulation)
    await db.execute(delete(BiometricReading).where(BiometricReading.patient_uuid == patient_uuid))

    # Seed 7 days × 24 h = 168 realistic readings using a sine-wave model
    readings = []
    for i in range(168):
        ts = now - timedelta(hours=167 - i)
        hour_phase = math.sin(ts.hour * math.pi / 12)
        week_factor = (i % 7 - 3) / 3.0

        hr = int(max(50, min(110, round(72 + hour_phase * 12 + week_factor * 2))))
        spo2 = int(max(95, min(100, round(97.5 + hour_phase * 0.5))))
        hrv = int(max(20, min(70, round(42 + hour_phase * 15 + week_factor * 3))))

        readings.append(BiometricReading(patient_uuid=patient_uuid, ts=ts, hr=hr, spo2=spo2, hrv=hrv))

    db.add_all(readings)
    await db.flush()

    # When Kafka is configured, also publish the most recent reading to the IoT
    # topic so the downstream anomaly pipeline (consumer + LSTM detector) sees
    # the simulated data flow end-to-end. The DB row above remains the source
    # of truth — the consumer's INSERT becomes a duplicate that is ignored
    # because of the (patient_uuid, ts) uniqueness imposed by the seed loop.
    latest = readings[-1]
    await publish_reading(
        {
            "device_id": f"SIMULATOR-{patient_uuid}",
            "patient_uuid": str(patient_uuid),
            "hr": latest.hr,
            "spo2": latest.spo2,
            "hrv": latest.hrv,
            "timestamp": int(latest.ts.timestamp()),
        }
    )

    return DeviceStatus(paired=True, last_sync=now, battery=85)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_vitals(
    batch: IngestBatch,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> IngestResponse:
    """
    Ingest a batch of wearable readings from the patient's phone.

    The mobile app reads vitals from Health Connect / HealthKit (or direct BLE)
    and posts them here. Samples missing hr or spo2 are dropped. HRV is
    optional — Mi Fitness does not publish HRV to Health Connect, so most
    Mi Band 7 Pro samples arrive without it. Duplicate timestamps for the
    same patient are skipped (idempotent retries from the phone).
    """
    patient_uuid = uuid.UUID(current_user.sub)
    now = datetime.now(timezone.utc)

    patient = (
        await db.execute(select(Patient).where(Patient.patient_uuid == patient_uuid))
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient record not found — contact your administrator.",
        )

    device = (
        await db.execute(select(IotDevice).where(IotDevice.patient_uuid == patient_uuid))
    ).scalar_one_or_none()
    if device is None:
        device = IotDevice(
            patient_uuid=patient_uuid,
            paired=True,
            last_sync=now,
            battery=batch.battery,
        )
        db.add(device)
    else:
        device.paired = True
        device.last_sync = now
        if batch.battery is not None:
            device.battery = batch.battery

    accepted = 0
    dropped = 0

    if not batch.samples:
        await db.flush()
        return IngestResponse(accepted=0, dropped=0)

    existing_ts = set(
        (
            await db.execute(
                select(BiometricReading.ts).where(
                    BiometricReading.patient_uuid == patient_uuid,
                    BiometricReading.ts.in_([s.ts for s in batch.samples]),
                )
            )
        ).scalars().all()
    )

    for sample in batch.samples:
        if sample.hr is None or sample.spo2 is None:
            dropped += 1
            continue
        if sample.ts in existing_ts:
            dropped += 1
            continue
        db.add(BiometricReading(
            patient_uuid=patient_uuid,
            ts=sample.ts,
            hr=sample.hr,
            spo2=sample.spo2,
            hrv=sample.hrv,
        ))
        existing_ts.add(sample.ts)
        accepted += 1

        await publish_reading({
            "device_id": batch.device_id,
            "patient_uuid": str(patient_uuid),
            "hr": sample.hr,
            "spo2": sample.spo2,
            "hrv": sample.hrv,
            "timestamp": int(sample.ts.timestamp()),
        })

    await db.flush()
    return IngestResponse(accepted=accepted, dropped=dropped)
