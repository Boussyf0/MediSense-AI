"""
Anomaly Detection endpoints — Sprint 7 (US-28).

GET  /anomalies/recent/{patient_uuid}  — latest window scores for a patient (staff)
GET  /anomalies/summary                — patient-facing aggregate + insight text
POST /anomalies/detect                 — score a manually submitted window (demo/fallback)
"""
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_any_staff, require_doctor, require_patient
from app.db.models.biometric_reading import BiometricReading
from app.db.session import get_db
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
    narrative: str | None = None


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


class AnomalySummaryResponse(BaseModel):
    summary: str
    hrv_trend_pct: float | None
    mean_hr_7d: float | None
    mean_spo2_7d: float | None
    sample_count: int


def _build_insight(
    hrv_trend_pct: float | None,
    mean_hr: float | None,
    mean_spo2: float | None,
    samples: int,
) -> str:
    if samples == 0:
        return (
            "Aucune donnée biométrique pour le moment. "
            "Synchronisez votre bracelet pour obtenir des conseils personnalisés."
        )
    parts: list[str] = []
    if hrv_trend_pct is not None and hrv_trend_pct <= -10:
        parts.append(
            f"Votre HRV est en baisse de {abs(int(hrv_trend_pct))}% sur 7 jours — "
            "compatible avec un déficit de récupération. Visez 7h de sommeil cette nuit."
        )
    elif hrv_trend_pct is not None and hrv_trend_pct >= 10:
        parts.append(
            f"Votre HRV progresse de {int(hrv_trend_pct)}% sur 7 jours — "
            "bonne récupération, continuez ainsi."
        )
    if mean_spo2 is not None and mean_spo2 < 95:
        parts.append(
            f"SpO₂ moyenne basse ({mean_spo2:.0f}%) — consultez si la tendance persiste."
        )
    if mean_hr is not None and mean_hr > 95:
        parts.append(
            f"Fréquence cardiaque moyenne élevée ({mean_hr:.0f} bpm) — "
            "limitez caféine et stress."
        )
    if not parts:
        return "Vos signes vitaux restent dans les normes attendues. Bon travail."
    return " ".join(parts)


@router.get(
    "/summary",
    response_model=AnomalySummaryResponse,
    summary="Patient-facing 7-day biometric summary + AI insight",
)
async def get_patient_summary(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> AnomalySummaryResponse:
    """
    Aggregates the patient's last 7 days of biometric readings into a
    short French insight string. No model call — pure heuristic over
    HRV trend, mean HR, mean SpO2 — so it stays fast and works without
    the LSTM artefact being loaded.
    """
    patient_uuid = _uuid.UUID(current_user.sub)
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(hours=24)

    rows = (
        await db.execute(
            select(BiometricReading)
            .where(
                BiometricReading.patient_uuid == patient_uuid,
                BiometricReading.ts >= week_ago,
            )
        )
    ).scalars().all()

    if not rows:
        return AnomalySummaryResponse(
            summary=_build_insight(None, None, None, 0),
            hrv_trend_pct=None,
            mean_hr_7d=None,
            mean_spo2_7d=None,
            sample_count=0,
        )

    last_24h = [r for r in rows if r.ts >= day_ago]
    prior = [r for r in rows if r.ts < day_ago]

    mean_hr = sum(r.hr for r in rows) / len(rows)
    mean_spo2 = sum(r.spo2 for r in rows) / len(rows)

    hrv_trend_pct: float | None = None
    recent_hrv_vals = [r.hrv for r in last_24h if r.hrv is not None]
    prior_hrv_vals = [r.hrv for r in prior if r.hrv is not None]
    if recent_hrv_vals and prior_hrv_vals:
        recent_hrv = sum(recent_hrv_vals) / len(recent_hrv_vals)
        prior_hrv = sum(prior_hrv_vals) / len(prior_hrv_vals)
        if prior_hrv > 0:
            hrv_trend_pct = round((recent_hrv - prior_hrv) / prior_hrv * 100, 1)

    return AnomalySummaryResponse(
        summary=_build_insight(hrv_trend_pct, mean_hr, mean_spo2, len(rows)),
        hrv_trend_pct=hrv_trend_pct,
        mean_hr_7d=round(mean_hr, 1),
        mean_spo2_7d=round(mean_spo2, 1),
        sample_count=len(rows),
    )


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
