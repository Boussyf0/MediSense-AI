"""
Patient schemas — Pydantic models for Sprint 2 RGPD endpoints.

Schemas defined here:
  ConsentUpdate        — PATCH /patients/{uuid}/consent request body (US-06)
  ConsentResponse      — PATCH /patients/{uuid}/consent response
  ConsentLogEntry      — single entry in consent history (used by export)
  AuditLogExportEntry  — reduced audit row exposed in the patient export
                         (hides actor_uuid and ip_address — admin-only fields)
  PatientDataExport    — GET /patients/{uuid}/data/export response (US-07)
                         Admin-only endpoint (require_admin).
  ErasureResponse      — DELETE /patients/{uuid} response (US-08)

NOTE ON AUDIT SCHEMAS:
  The full AuditLogEntry (with actor_uuid, ip_address, user_agent) lives in
  schemas/admin.py and is used by the paginated admin audit endpoint (US-46).
  AuditLogExportEntry defined here is a deliberately reduced view: patients
  can see *that* their data was accessed and *by which role*, but not the
  full actor identity or IP — that is admin-only information.
"""
from datetime import datetime
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, field_validator


class ConsentUpdate(BaseModel):
    """
    Request body for PATCH /patients/{patient_uuid}/consent.

    Only the fields provided are updated — fields set to None are ignored.
    This lets a caller update a single consent flag without touching others.

    channel      : how the consent was collected (required for RGPD accountability)
    cgu_version  : version of the CGU/Terms the patient accepted (optional)
    """
    consent_iot: Optional[bool] = None
    consent_nlp: Optional[bool] = None
    consent_sharing: Optional[bool] = None
    sms_opt_out: Optional[bool] = None
    channel: str = "web"
    cgu_version: Optional[str] = None

    @field_validator("channel")
    @classmethod
    def channel_must_be_valid(cls, v: str) -> str:
        allowed = {"app", "web", "paper"}
        if v not in allowed:
            raise ValueError(f"channel must be one of {allowed}")
        return v

    @field_validator("cgu_version")
    @classmethod
    def cgu_version_max_length(cls, v: str | None) -> str | None:
        if v and len(v) > 20:
            raise ValueError("cgu_version max length is 20 characters")
        return v


class ConsentResponse(BaseModel):
    """Current consent state after update."""
    patient_uuid: UUID
    consent_iot: bool
    consent_nlp: bool
    consent_sharing: bool
    sms_opt_out: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConsentLogEntry(BaseModel):
    """Single entry from public.consent_logs (used in data export)."""
    consent_type: str    # 'iot' | 'nlp' | 'sharing'
    action: str          # 'granted' | 'revoked'
    channel: str
    cgu_version: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PatientRecord(BaseModel):
    """Pseudonymized patient record (no civil identity)."""
    patient_uuid: UUID
    consent_iot: bool
    consent_nlp: bool
    consent_sharing: bool
    sms_opt_out: bool
    birth_year: Optional[int]
    sex: Optional[str]
    city_code: Optional[str]
    chronic_conditions: Optional[List[str]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientDataExport(BaseModel):
    """
    Response for GET /patients/{patient_uuid}/data/export (US-07).

    RGPD Art. 20 — Right to data portability.
    Admin-only endpoint: formal data export requests are handled by the DPO,
    not by individual doctors. Returns a machine-readable export of all
    pseudonymized data held about the patient.

    NOTE: Civil identity (name, phone, email) is NOT included here.
    That data lives in secure.patients_identity and requires DPO-level
    decryption (handled in a separate Sprint 5 DPO endpoint).
    """
    exported_at: datetime
    patient: PatientRecord
    consent_history: List[ConsentLogEntry]
    access_log: List["AuditLogExportEntry"]


class AuditLogExportEntry(BaseModel):
    """Subset of audit log fields exposed in the patient data export."""
    action: str
    resource_type: str
    actor_role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ErasureResponse(BaseModel):
    """
    Response for DELETE /patients/{patient_uuid} (US-08).

    RGPD Art. 17 — Right to erasure ("right to be forgotten").

    What happens on erasure:
      1. public.patients: is_active=False, ML fields anonymized (birth_year,
         sex, city_code, chronic_conditions cleared), consent flags reset
      2. secure.patients_identity: row deleted (civil identity removed)
      3. public.audit_logs: erasure event recorded (the log itself is kept
         for legal accountability — RGPD allows keeping audit trails)

    The patient_uuid record is kept in public.patients (is_active=False)
    to maintain referential integrity with existing appointment/audit records.
    """
    patient_uuid: UUID
    erased_at: datetime
    message: str


# Rebuild for forward reference
PatientDataExport.model_rebuild()
