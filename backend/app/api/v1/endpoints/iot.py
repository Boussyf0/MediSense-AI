import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_patient
from app.db.models.biometric_reading import BiometricReading
from app.db.models.iot_device import IotDevice
from app.db.session import get_db
from app.schemas.iot import DeviceStatus, VitalPoint

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
