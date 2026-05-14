"""
Anomaly Detection endpoints — Sprint 7 (US-28).

GET  /anomalies/recent/{patient_uuid}  — latest window scores for a patient
POST /anomalies/detect                 — score a manually submitted window (demo/fallback)
"""
import uuid as _uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.dependencies import TokenPayload, require_any_staff, require_doctor
from app.services.anomaly_detector import get_recent_scores, ingest_reading

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


class VitalReading(BaseModel):
    hr: float = Field(ge=0, le=300)
    spo2: float = Field(ge=0, le=100)
    hrv: float = Field(ge=0, le=500)
    temperature: float = Field(ge=30.0, le=45.0)


class DetectRequest(BaseModel):
    patient_uuid: str
    window_minutes: int = Field(default=5, ge=1, le=60)
    vitals: list[VitalReading] = Field(min_length=1)


class AnomalyScoreResponse(BaseModel):
    patient_uuid: str
    score_5m: float | None
    score_60m: float | None
    alert_critical: bool
    trend_elevated: bool
    readings_5m: int = 0
    readings_60m: int = 0


@router.get(
    "/recent/{patient_uuid}",
    response_model=AnomalyScoreResponse,
    summary="Get latest anomaly window scores for a patient",
)
async def get_recent_anomalies(
    patient_uuid: str,
    _: TokenPayload = Depends(require_any_staff),
) -> dict[str, Any]:
    try:
        _uuid.UUID(patient_uuid)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid patient_uuid")

    return await get_recent_scores(patient_uuid)


@router.post(
    "/detect",
    response_model=AnomalyScoreResponse,
    summary="Score a manually submitted biometric window",
)
async def detect_anomaly(
    body: DetectRequest,
    _: TokenPayload = Depends(require_doctor),
) -> dict[str, Any]:
    try:
        _uuid.UUID(body.patient_uuid)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid patient_uuid")

    vitals_dicts = [v.model_dump() for v in body.vitals]
    result = await ingest_reading(body.patient_uuid, vitals_dicts[-1])
    result["patient_uuid"]  = body.patient_uuid
    result["readings_5m"]   = len(vitals_dicts)
    result["readings_60m"]  = len(vitals_dicts)
    return result
