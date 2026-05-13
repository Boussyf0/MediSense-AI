"""
Patient endpoints — Sprint 2 RGPD & Consentement.

Endpoints:
  PATCH  /patients/{patient_uuid}/consent      US-06 — granular consent update
  GET    /patients/{patient_uuid}/data/export  US-07 — RGPD data portability export
  DELETE /patients/{patient_uuid}              US-08 — right to erasure

ACCESS CONTROL:
  All three endpoints require at minimum doctor or admin role.
  The patient-facing (self-service) consent endpoint will be added when
  patient authentication is implemented (Sprint 3 or 4).

  For the demo and PFE, doctors update consent on the patient's behalf
  (the most common clinical workflow in Moroccan practice).

RGPD ARTICLES COVERED:
  Art. 7  — Consent conditions (US-06)
  Art. 20 — Right to data portability (US-07)
  Art. 17 — Right to erasure (US-08)
  Art. 30 — Records of processing activities (audit log in every endpoint)
"""
import uuid
from datetime import datetime, timezone
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.db.session import get_db
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient, PatientIdentity
from app.db.models.audit_log import AuditLog, ConsentLog
from app.db.models.conversation import Conversation
from app.core.conversation_cache import clear_patient_conversations
from app.core.dependencies import require_doctor, require_admin, require_patient, TokenPayload
from app.core.audit import log_audit, log_consent
from app.schemas.patient import (
    ConsentUpdate,
    ConsentResponse,
    PatientDataExport,
    PatientRecord,
    ConsentLogEntry,
    AuditLogExportEntry,
    ErasureResponse,
)

router = APIRouter(prefix="/patients", tags=["Patients"])


class PatientListItem(BaseModel):
    patient_uuid: uuid.UUID
    birth_year: int | None
    sex: str | None
    city_code: str | None
    chronic_conditions: list[str] | None
    is_active: bool
    last_appointment_at: datetime | None
    next_appointment_at: datetime | None


class PatientListResponse(BaseModel):
    items: List[PatientListItem]
    total: int
    limit: int
    offset: int


@router.get(
    "",
    response_model=PatientListResponse,
    summary="List patients (clinical roster) — doctor/admin only",
)
async def list_patients(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[TokenPayload, Depends(require_doctor)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    only_active: bool = Query(default=True),
):
    """
    Paginated list of pseudonymized patient records.

    Each row joins the patient row with last/next appointment timestamps so the
    web roster can render a usable table without an N+1 round-trip.
    """
    query = select(Patient)
    if only_active:
        query = query.where(Patient.is_active.is_(True))

    total = (
        await db.execute(
            select(func.count()).select_from(query.subquery())
        )
    ).scalar_one()

    rows = (
        await db.execute(
            query.order_by(Patient.updated_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()

    items: List[PatientListItem] = []
    now = datetime.now(timezone.utc)
    for patient in rows:
        last_appt = (
            await db.execute(
                select(func.max(Appointment.scheduled_at)).where(
                    Appointment.patient_uuid == patient.patient_uuid,
                    Appointment.scheduled_at <= now,
                )
            )
        ).scalar_one_or_none()
        next_appt = (
            await db.execute(
                select(func.min(Appointment.scheduled_at)).where(
                    Appointment.patient_uuid == patient.patient_uuid,
                    Appointment.scheduled_at > now,
                )
            )
        ).scalar_one_or_none()
        items.append(
            PatientListItem(
                patient_uuid=patient.patient_uuid,
                birth_year=patient.birth_year,
                sex=patient.sex,
                city_code=patient.city_code,
                chronic_conditions=patient.chronic_conditions,
                is_active=patient.is_active,
                last_appointment_at=last_appt,
                next_appointment_at=next_appt,
            )
        )

    return PatientListResponse(items=items, total=int(total), limit=limit, offset=offset)


# ── Patient self-service consent (mobile app) ─────────────

@router.patch(
    "/me/consent",
    response_model=ConsentResponse,
    summary="Patient self-service consent update (mobile)",
    description=(
        "Patients update their own RGPD consent flags from the mobile app. "
        "Patient UUID is derived from the JWT — no path parameter needed. "
        "Uses the same audit trail logic as the doctor-managed endpoint."
    ),
)
async def update_own_consent(
    body: ConsentUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_patient)],
):
    patient_uuid = uuid.UUID(current_user.sub)

    result = await db.execute(select(Patient).where(Patient.patient_uuid == patient_uuid))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    consent_fields = {
        "iot": (patient.consent_iot, body.consent_iot),
        "nlp": (patient.consent_nlp, body.consent_nlp),
        "sharing": (patient.consent_sharing, body.consent_sharing),
    }

    changed = False
    for consent_type, (old_val, new_val) in consent_fields.items():
        if new_val is None or new_val == old_val:
            continue
        action = "granted" if new_val else "revoked"
        await log_consent(
            db=db,
            patient_uuid=patient_uuid,
            consent_type=consent_type,
            action=action,
            channel=body.channel,
            request=request,
            cgu_version=body.cgu_version,
        )
        setattr(patient, f"consent_{consent_type}", new_val)
        changed = True

    if body.sms_opt_out is not None and body.sms_opt_out != patient.sms_opt_out:
        patient.sms_opt_out = body.sms_opt_out
        changed = True

    if not changed:
        return ConsentResponse.model_validate(patient)

    await log_audit(
        db=db,
        actor=current_user,
        request=request,
        action="CONSENT",
        resource_type="patient",
        resource_uuid=patient_uuid,
    )
    await db.flush()
    return ConsentResponse.model_validate(patient)


# ── US-06 — Granular Consent Update ──────────────────────

@router.patch(
    "/{patient_uuid}/consent",
    response_model=ConsentResponse,
    summary="US-06 — Update patient consent flags",
    description=(
        "Update one or more RGPD consent flags for a patient. "
        "Core consent changes (iot/nlp/sharing) are logged to immutable consent_logs; "
        "sms_opt_out preference remains audit-tracked via audit_logs. "
        "RGPD Art. 7 — consent must be specific, informed, and revocable."
    ),
)
async def update_consent(
    patient_uuid: uuid.UUID,
    body: ConsentUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_doctor)],
):
    """
    Granular consent update with full audit trail.

    Logic:
      1. Load patient — 404 if not found
      2. For each consent flag in the request body:
         - If the value changed → write a consent_log entry
         - Update the patient record
      3. Write an audit_log entry for the whole operation
      4. Return the updated consent state

    WHY CHECK IF VALUE CHANGED?
      We only log 'granted' or 'revoked' when the value actually changes.
      Sending the same value twice (e.g., consent_iot=True when already True)
      must not create a spurious log entry — that would pollute the audit trail.
    """
    result = await db.execute(
        select(Patient).where(Patient.patient_uuid == patient_uuid)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    # Map of consent field name → (old value, new value)
    # Note: sms_opt_out is stored in patients but not in consent_logs because
    # the consent_logs DB constraint currently tracks only iot/nlp/sharing.
    consent_fields = {
        "iot": (patient.consent_iot, body.consent_iot),
        "nlp": (patient.consent_nlp, body.consent_nlp),
        "sharing": (patient.consent_sharing, body.consent_sharing),
    }

    changed = False
    for consent_type, (old_val, new_val) in consent_fields.items():
        if new_val is None:
            continue   # field not included in request → skip
        if new_val == old_val:
            continue   # no change → skip (don't pollute audit trail)

        # Value changed → log it
        action = "granted" if new_val else "revoked"
        await log_consent(
            db=db,
            patient_uuid=patient_uuid,
            consent_type=consent_type,
            action=action,
            channel=body.channel,
            request=request,
            cgu_version=body.cgu_version,
        )

        # Apply change to ORM object
        setattr(patient, f"consent_{consent_type}", new_val)
        changed = True

    # SMS preference is still audited through audit_logs (action=CONSENT),
    # but not inserted into consent_logs to preserve its strict enum contract.
    if body.sms_opt_out is not None and body.sms_opt_out != patient.sms_opt_out:
        patient.sms_opt_out = body.sms_opt_out
        changed = True

    if not changed:
        # Return current state without writing anything — idempotent
        return ConsentResponse.model_validate(patient)

    # Record the overall operation in the audit log
    await log_audit(
        db=db,
        actor=current_user,
        request=request,
        action="CONSENT",
        resource_type="patient",
        resource_uuid=patient_uuid,
    )

    # Flush so the DB-managed onupdate trigger populates Patient.updated_at
    # before we serialise it into the response. Without this the response
    # would return the pre-update timestamp even though the row was changed.
    await db.flush()
    return ConsentResponse.model_validate(patient)


# ── US-07 — RGPD Data Export ──────────────────────────────

@router.get(
    "/{patient_uuid}/data/export",
    response_model=PatientDataExport,
    summary="US-07 — Export patient data (RGPD Art. 20)",
    description=(
        "Export all pseudonymized data held about a patient in machine-readable JSON. "
        "Includes: consent state, demographics, consent change history, and access log. "
        "Civil identity (name, phone) is NOT included — requires DPO-level decryption (Sprint 5). "
        "Admin-only: exporting another person's data is a sensitive operation."
    ),
)
async def export_patient_data(
    patient_uuid: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_admin)],
):
    """
    RGPD Art. 20 — Right to data portability.

    Returns a complete, machine-readable export of pseudonymized data.
    Every export is logged (the patient can later ask "who exported my data?").

    DS/AI NOTE:
      The 'chronic_conditions' list in the patient record is used as a feature
      vector by the no-show prediction model (XGBoost, Sprint 7).
      Exporting it here shows the patient exactly what the ML model sees.
    """
    result = await db.execute(
        select(Patient).where(Patient.patient_uuid == patient_uuid)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    # Fetch consent history (most recent 100 entries)
    consent_result = await db.execute(
        select(ConsentLog)
        .where(ConsentLog.patient_uuid == patient_uuid)
        .order_by(ConsentLog.created_at.desc())
        .limit(100)
    )
    consent_history = consent_result.scalars().all()

    # Log the export BEFORE querying the access log so this event appears
    # in the response's access_log section (it's flushed by the SELECT below).
    await log_audit(
        db=db,
        actor=current_user,
        request=request,
        action="EXPORT",
        resource_type="patient",
        resource_uuid=patient_uuid,
    )
    # Flush the EXPORT entry to the DB (same transaction) so the subsequent
    # SELECT picks it up in the access_log results.
    await db.flush()

    # Fetch access log for this patient (most recent 100 entries)
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.resource_uuid == patient_uuid)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    access_log = audit_result.scalars().all()

    return PatientDataExport(
        exported_at=datetime.now(timezone.utc),
        patient=PatientRecord.model_validate(patient),
        consent_history=[ConsentLogEntry.model_validate(c) for c in consent_history],
        access_log=[AuditLogExportEntry.model_validate(a) for a in access_log],
    )


# ── US-08 — Right to Erasure ──────────────────────────────

@router.delete(
    "/{patient_uuid}",
    response_model=ErasureResponse,
    summary="US-08 — Erase patient data (RGPD Art. 17)",
    description=(
        "Erase a patient's personal data. "
        "Two-step operation: (1) delete civil identity from secure schema, "
        "(2) anonymize pseudonymized record in public schema. "
        "The patient UUID is preserved for audit trail integrity. "
        "Admin-only — irreversible operation."
    ),
)
async def erase_patient(
    patient_uuid: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[TokenPayload, Depends(require_admin)],
):
    """
    RGPD Art. 17 — Right to erasure.

    Step 1 — Delete from secure.patients_identity
      The encrypted civil identity (name, phone, email) is permanently deleted.
      This is the "real" erasure — without the identity, the pseudonymized
      record in public.patients cannot be linked back to a real person.

    Step 2 — Anonymize public.patients
      ML features (birth_year, sex, city_code, chronic_conditions) are cleared.
      Consent flags are reset to False.
      is_active is set to False (soft delete — UUID preserved for referential
      integrity with existing appointments and audit records).

    Step 3 — Log the erasure
      The audit log records who requested the erasure and when.
      Keeping the audit record is RGPD-compliant: Art. 17 allows organizations
      to retain minimal data needed to demonstrate compliance.

    WHY NOT HARD DELETE THE patient ROW?
      - Foreign keys: public.appointments.patient_uuid, public.consent_logs.patient_uuid,
        public.audit_logs.resource_uuid all reference this UUID.
      - Hard-deleting would cascade or fail, destroying appointment history
        which may be needed for medical and legal retention obligations.
      - After anonymization, the patient row contains no personal data.
    """
    result = await db.execute(
        select(Patient).where(Patient.patient_uuid == patient_uuid)
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    if not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient has already been erased",
        )

    conv_result = await db.execute(
        select(Conversation.id).where(Conversation.patient_id == patient_uuid)
    )
    conversation_ids = [str(row.id) for row in conv_result.all()]
    await clear_patient_conversations(str(patient_uuid), conversation_ids)

    # Step 1 — Delete civil identity from secure schema
    await db.execute(
        delete(PatientIdentity).where(PatientIdentity.patient_uuid == patient_uuid)
    )

    # Step 2 — Anonymize the pseudonymized record
    patient.is_active = False
    patient.birth_year = None
    patient.sex = None
    patient.city_code = None
    patient.chronic_conditions = None
    patient.consent_iot = False
    patient.consent_nlp = False
    patient.consent_sharing = False
    patient.sms_opt_out = True

    # Step 3 — Log the erasure
    await log_audit(
        db=db,
        actor=current_user,
        request=request,
        action="DELETE",
        resource_type="patient",
        resource_uuid=patient_uuid,
    )

    erased_at = datetime.now(timezone.utc)
    return ErasureResponse(
        patient_uuid=patient_uuid,
        erased_at=erased_at,
        message=(
            "Patient data erased. Civil identity deleted from secure storage. "
            "Pseudonymized record anonymized. UUID retained for audit trail integrity."
        ),
    )
