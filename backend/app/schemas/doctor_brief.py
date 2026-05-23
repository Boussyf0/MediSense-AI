"""
Schemas for the doctor's 5-minute pre-consult brief.

Composed view served by GET /api/v1/doctor/agenda/{appointment_id}/brief.
Combines patient identity, latest vitals, anomaly narrative, recent
symptom mentions, and no-show risk in a single round-trip so the
clinician can scan everything before the visit starts.
"""
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PatientCard(BaseModel):
    patient_uuid: UUID
    display_name: str | None = None
    age: int | None = None
    sex: str | None = None
    chronic_conditions: list[str] = Field(default_factory=list)


class VitalsSnapshot(BaseModel):
    """Most recent biometric reading (24h window). All optional — patient may have no IoT."""
    hr: int | None = None
    spo2: int | None = None
    hrv: int | None = None
    measured_at: datetime | None = None
    samples_24h: int = 0


class AnomalyFlag(BaseModel):
    """Live anomaly signal from the LSTM windows + deterministic narrative."""
    score_5m: float | None = None
    score_60m: float | None = None
    alert_critical: bool = False
    trend_elevated: bool = False
    narrative: str | None = None


class SymptomMention(BaseModel):
    """Last user-authored chat message — what the patient said in their own words."""
    content: str
    created_at: datetime


class NoShowRisk(BaseModel):
    probability: float | None = None
    risk_color: str | None = None       # 'red' | 'orange' | 'green'
    model_version: str | None = None


class DoctorBriefResponse(BaseModel):
    appointment_uuid: UUID
    scheduled_at: datetime
    patient: PatientCard
    vitals: VitalsSnapshot
    anomaly: AnomalyFlag
    recent_symptoms: list[SymptomMention] = Field(default_factory=list)
    noshow: NoShowRisk
    generated_at: datetime
