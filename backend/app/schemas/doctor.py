"""
Pydantic schemas for doctor-facing DPA endpoints (US-41, US-42).

WHY SEPARATE SCHEMAS FROM MODELS?
  SQLAlchemy models describe how data is stored in PostgreSQL.
  Pydantic schemas describe what the API sends and receives over HTTP.
  Keeping them separate allows:
    1. The API contract to change without touching the DB schema (and vice versa).
    2. Field-level validation (e.g., status must be one of 4 values).
    3. Clean serialization of nested structures (actions list inside summary).
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── IoT Anomaly (read-only, from BiometricAnomaly model) ────────────────────

class IoTAnomalyOut(BaseModel):
    metric: str
    value: float
    unit: str = ""
    threshold: float
    severity: str           # 'mild' | 'moderate' | 'critical'
    detected_at: str | None = None


class IoTSummaryOut(BaseModel):
    latest_anomalies: list[IoTAnomalyOut] = []
    trend: str = "stable"   # 'stable' | 'improving' | 'declining' | 'critical'


# ── Recommended Action ───────────────────────────────────────────────────────

class RecommendedAction(BaseModel):
    action: str             # 'prescribe' | 'monitor' | 'refer' | 'alert'
    # Prescribe
    medication: str | None = None
    dosage: str | None = None
    reasoning: str | None = None
    # Monitor
    metric: str | None = None
    frequency: str | None = None
    # Refer
    specialist: str | None = None
    urgency: str | None = None  # 'routine' | 'urgent'
    # Alert
    message: str | None = None


class AgentActionOut(BaseModel):
    """Action row with persistent ID and review state (for UI mutations)."""
    id: UUID
    action_type: str
    payload: dict[str, Any]
    modified_payload: dict[str, Any] | None = None
    status: str


# ── DPA Summary (US-41 GET response) ────────────────────────────────────────

class DPASummaryOut(BaseModel):
    """Full DPA summary returned by GET /doctor/patient/{uuid}/dpa-summary."""
    summary_id: UUID
    patient_uuid: UUID
    symptoms: list[str] = []
    iot_summary: IoTSummaryOut = Field(default_factory=IoTSummaryOut)
    recommended_actions: list[RecommendedAction] = []
    agent_actions: list[AgentActionOut] = []
    confidence: float = 0.0
    data_freshness_minutes: int = 0
    status: str = "PENDING"     # PENDING | APPROVED | MODIFIED | REJECTED
    version: int = 1
    created_at: datetime | None = None

    class Config:
        from_attributes = True


# ── Approval / Rejection (US-42) ────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    """
    Body for POST /dpa-summary/{summary_id}/approve.

    doctor_note is optional — doctor can add clinical reasoning.
    edited_actions replaces the AI recommendations with doctor edits.
    If edited_actions is None → no changes, AI recommendations used as-is.
    """
    doctor_note: str | None = None
    edited_actions: list[RecommendedAction] | None = None


class RejectionRequest(BaseModel):
    """Body for POST /dpa-summary/{summary_id}/reject."""
    doctor_note: str = Field(
        ...,
        min_length=10,
        description="Doctor must provide a reason for rejection (min 10 chars)",
    )


class DPAActionDecision(BaseModel):
    """Body for PATCH /dpa-summary/{summary_id}/action/{action_id}."""
    status: str = Field(..., pattern="^(approved|rejected|modified)$")
    modified_payload: dict[str, Any] | None = None


class ApprovalResponse(BaseModel):
    """Response after approve/reject/modify."""
    summary_id: UUID
    status: str
    version: int
    reviewed_at: datetime | None = None
    message: str
