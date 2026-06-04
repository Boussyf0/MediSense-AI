"""
CRM endpoints — Sprint 6, US-43.

Secretary-facing API to manage Salesforce task synchronisation.
All three endpoints require secretary or admin role (RBAC).

Design constraints:
  - CRM retries are fire-and-forget (asyncio.create_task) — response
    returns immediately; Salesforce call happens in background.
  - All writes use await db.flush() — never commit inside endpoint.
  - All data access is recorded in audit_logs (RGPD Art. 30).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.config import get_settings
from app.core.dependencies import TokenPayload, require_role, require_secretary
from app.db.models.appointment import Appointment
from app.db.models.device_token import DeviceToken
from app.db.models.user import User
from app.db.models.sms_reminder_log import SmsReminderLog
from app.db.models.patient import Patient
from app.db.session import AsyncSessionLocal, get_db
from app.services.fcm_service import send_to_tokens
from app.services.salesforce_client import send_crm_event
from app.services.sms_reminder import (
    _build_sms_message,
    _get_patient_phone_number,
    _mark_sms_sent_now,
    _release_sms_slot,
    _reserve_sms_slot,
    _send_sms,
)
from app.schemas.crm import (
    CRMRetryRequest,
    CRMRetryResponse,
    CRMTaskListResponse,
    CRMTaskOut,
    CRMTaskPatch,
)

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/tasks", response_model=CRMTaskListResponse)
async def list_crm_tasks(
    request: Request,
    crm_sync_status: str | None = Query(default=None, description="Filter by sync status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_secretary),
) -> CRMTaskListResponse:
    """List appointments with CRM sync status. Secretary/admin only."""
    try:
        base_q = select(Appointment)
        if crm_sync_status is not None:
            base_q = base_q.where(Appointment.crm_sync_status == crm_sync_status)

        count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
        total = count_result.scalar_one()

        rows_result = await db.execute(
            base_q.order_by(Appointment.scheduled_at.desc()).limit(limit).offset(offset)
        )
        rows = rows_result.scalars().all()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRM database unavailable — run: alembic upgrade head",
        ) from exc

    # Resolve patient names from the users table
    patient_names: dict[uuid.UUID, str] = {}
    patient_ids = {r.patient_uuid for r in rows}
    if patient_ids:
        name_rows = await db.execute(
            select(User.user_uuid, User.first_name, User.last_name, User.email)
            .where(User.user_uuid.in_(patient_ids))
        )
        for user_uuid, first_name, last_name, email in name_rows.all():
            label = " ".join(p for p in [first_name, last_name] if p) or email
            patient_names[user_uuid] = label

    items = []
    for r in rows:
        task = CRMTaskOut.model_validate(r)
        task.patient_name = patient_names.get(r.patient_uuid)
        items.append(task)

    await log_audit(db, current_user, request, action="READ", resource_type="crm_task")
    return CRMTaskListResponse(total=total, items=items)


@router.patch("/tasks/{appointment_uuid}", response_model=CRMTaskOut)
async def update_crm_task(
    appointment_uuid: uuid.UUID,
    body: CRMTaskPatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_secretary),
) -> CRMTaskOut:
    """Update salesforce_task_id or crm_sync_status. Secretary/admin only."""
    result = await db.execute(
        select(Appointment).where(Appointment.appointment_uuid == appointment_uuid)
    )
    appt = result.scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if body.salesforce_task_id is not None:
        appt.salesforce_task_id = body.salesforce_task_id
    if body.crm_sync_status is not None:
        appt.crm_sync_status = body.crm_sync_status

    await db.flush()
    await log_audit(db, current_user, request, action="WRITE",
                    resource_type="crm_task", resource_uuid=appointment_uuid)
    return CRMTaskOut.model_validate(appt)


@router.post("/tasks/{appointment_uuid}/retry", response_model=CRMRetryResponse)
async def retry_crm_task(
    appointment_uuid: uuid.UUID,
    body: CRMRetryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_secretary),
) -> CRMRetryResponse:
    """Dispatch a non-blocking Salesforce retry for a failed task. Secretary/admin only."""
    result = await db.execute(
        select(Appointment).where(Appointment.appointment_uuid == appointment_uuid)
    )
    appt = result.scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if appt.crm_sync_status == "SENT" and not body.force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task already sent. Use force=true to retry anyway.",
        )

    settings = get_settings()
    if appt.crm_retry_count >= settings.SALESFORCE_MAX_RETRIES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Max retries ({settings.SALESFORCE_MAX_RETRIES}) reached for this task.",
        )

    # Fire-and-forget with a dedicated session so DB persist works after the
    # request session closes.  The background coroutine owns its own transaction.
    _appt_id = str(appt.appointment_uuid)
    _patient_id = str(appt.patient_uuid)
    _urgency = appt.urgency_flag

    async def _do_retry() -> None:  # pragma: no cover
        async with AsyncSessionLocal() as bg_db:
            try:
                await send_crm_event(
                    patient_id=_patient_id,
                    severity="routine",
                    appointment_id=_appt_id,
                    specialist_type=_urgency,
                    query_fr="[secretary-initiated retry]",
                    iot_triggered=False,
                    db=bg_db,
                )
                await bg_db.commit()
            except Exception:
                logger.error("CRM retry failed", exc_info=True)
                await bg_db.rollback()

    asyncio.create_task(_do_retry())

    appt.crm_sync_status = "PENDING"
    await db.flush()

    await log_audit(db, current_user, request, action="WRITE",
                    resource_type="crm_task", resource_uuid=appointment_uuid)

    return CRMRetryResponse(
        appointment_uuid=appointment_uuid,
        crm_correlation_id=appt.crm_correlation_id,
        crm_sync_status="PENDING",
        message="Retry dispatched asynchronously.",
    )


class SmsSendResponse(BaseModel):
    id: uuid.UUID
    appointment_uuid: uuid.UUID
    task_type: str
    status: str
    scheduled_for: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/sms/send/{appointment_uuid}", response_model=SmsSendResponse)
async def send_sms_reminder(
    appointment_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("doctor", "secretary", "admin")),
) -> SmsSendResponse:
    """
    Manual per-row SMS + FCM push (agenda "Envoyer" button).

    Honours patient opt-out and the global max-reminder cap, but bypasses the
    auto-dispatcher's no-show probability threshold — staff is taking an
    explicit clinical decision to remind this patient now.

    On success: SMS goes out via the configured webhook (mock if unset),
    a push notification is delivered to every registered device of the
    patient user, and `appointment.sms_reminders_sent` is incremented so
    the agenda counter updates on the next refetch.
    """
    appt = (
        await db.execute(
            select(Appointment).where(Appointment.appointment_uuid == appointment_uuid)
        )
    ).scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    now = datetime.now(timezone.utc)
    today = now.date()
    settings = get_settings()

    log = (
        await db.execute(
            select(SmsReminderLog).where(
                SmsReminderLog.appointment_uuid == appointment_uuid,
                SmsReminderLog.task_type == "sms_reminder",
                SmsReminderLog.scheduled_date == today,
            )
        )
    ).scalar_one_or_none()
    if log is not None and log.status == "sent":
        return SmsSendResponse.model_validate(log)
    if log is None:
        log = SmsReminderLog(
            appointment_uuid=appointment_uuid,
            task_type="sms_reminder",
            status="pending",
            scheduled_for=now,
            scheduled_date=today,
        )
        db.add(log)
        await db.flush()

    patient = (
        await db.execute(
            select(Patient).where(Patient.patient_uuid == appt.patient_uuid)
        )
    ).scalar_one_or_none()
    if patient is None or not patient.is_active:
        log.status = "failed"
        await db.flush()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient inactive ou introuvable")
    if patient.sms_opt_out:
        log.status = "skipped"
        await db.flush()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Patient a refusé les SMS")

    reserved = await _reserve_sms_slot(db, appointment_uuid, settings.SMS_REMINDER_MAX_COUNT)
    if reserved is None:
        log.status = "skipped"
        await db.flush()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nombre maximum de rappels atteint")

    phone = await _get_patient_phone_number(db, appt.patient_uuid)
    probability = float(appt.noshow_probability or 0.0)
    message_body = _build_sms_message(appt, probability)

    sms_error: str | None = None
    if phone:
        try:
            await _send_sms(
                phone_number=phone,
                message=message_body,
                appointment_uuid=appointment_uuid,
                patient_uuid=appt.patient_uuid,
            )
        except Exception as exc:  # provider / network failure
            sms_error = str(exc)
    else:
        sms_error = "missing_phone"

    tokens = (
        await db.execute(
            select(DeviceToken.token).where(DeviceToken.user_uuid == appt.patient_uuid)
        )
    ).scalars().all()
    pushed = await send_to_tokens(
        list(tokens),
        title="Rappel de rendez-vous",
        body=message_body,
        data={"appointment_uuid": str(appointment_uuid), "kind": "appointment_reminder"},
    )

    if sms_error and pushed == 0:
        await _release_sms_slot(db, appointment_uuid)
        log.status = "failed"
        await db.flush()
        if sms_error == "missing_phone":
            detail = "Patient sans numéro ni appareil enregistré"
        else:
            detail = f"Envoi échoué: {sms_error}"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    await _mark_sms_sent_now(db, appointment_uuid)
    log.status = "sent"
    await db.flush()
    return SmsSendResponse.model_validate(log)
