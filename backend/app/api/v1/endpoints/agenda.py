import logging
import uuid
from datetime import date as DateType, datetime, time, timezone
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_any_staff, require_role, require_secretary
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.user import User
from app.db.models.noshow_feedback import NoShowFeedback
from app.db.session import get_db
from app.services.noshow_predictor import (
    NoShowPredictor,
    ModelNotReadyError,
    FeatureValidationError,
    build_appointment_features,
    get_risk_color,
)
from app.services.sms_reminder import dispatch_smart_sms_reminders

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["ml"])


class AppointmentPrediction(BaseModel):
    appointment_uuid: uuid.UUID
    patient_uuid: uuid.UUID
    patient_name: str | None = None
    scheduled_at: datetime
    noshow_probability: float | None
    risk_color: str | None
    status: str
    sms_reminders_sent: int


class SMSDispatchItem(BaseModel):
    appointment_uuid: uuid.UUID
    risk_probability: float
    sent: bool
    reason: str
    sms_reminders_sent: int


class SMSDispatchSummary(BaseModel):
    total_candidates: int
    sent: int
    skipped: int
    items: List[SMSDispatchItem]


def _build_doctor_appointments_query(doctor_uuid: uuid.UUID, date: DateType | None):
    query = select(Appointment).where(Appointment.doctor_uuid == doctor_uuid)
    if date is not None:
        start_of_day = datetime.combine(date, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(date, time.max, tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_at.between(start_of_day, end_of_day))
    return query


@router.get("/no-show/batch", response_model=List[AppointmentPrediction])
async def get_noshow_predictions_batch(
    doctor_uuid: uuid.UUID = Query(...),
    date: DateType | None = Query(default=None),  # YYYY-MM-DD
    auto_send_smart_sms: bool = Query(
        default=False,
        description=(
            "If explicitly true, dispatch one additional reminder SMS for "
            "appointments with predicted no-show probability > 30%, while "
            "respecting opt-out and max-2 reminders."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(require_any_staff),
):
    """
    GET /api/v1/predictions/no-show/batch
    Returns a list of appointments for the Smart Agenda with no-show risks.

    Color coding:
    - green  < 20%
    - orange 20-40%
    - red    > 40%
    """
    result = await db.execute(_build_doctor_appointments_query(doctor_uuid, date))
    appointments = result.scalars().all()
    patient_names: dict[uuid.UUID, str] = {}
    if appointments:
        patient_ids = {appt.patient_uuid for appt in appointments}
        if patient_ids:
            rows = await db.execute(
                select(User.user_uuid, User.first_name, User.last_name, User.email)
                .where(User.user_uuid.in_(patient_ids))
            )
            for user_uuid, first_name, last_name, email in rows.all():
                label = " ".join(part for part in [first_name, last_name] if part) or email
                if label:
                    patient_names[user_uuid] = label

    if auto_send_smart_sms:
        await dispatch_smart_sms_reminders(db, appointments)
        for appointment in appointments:
            await db.refresh(appointment, attribute_names=["sms_reminders_sent"])

    predictions = []
    for appt in appointments:
        risk_probability = appt.noshow_probability
        risk_color = get_risk_color(risk_probability) if risk_probability is not None else None
        predictions.append(
            AppointmentPrediction(
                appointment_uuid=appt.appointment_uuid,
                patient_uuid=appt.patient_uuid,
                patient_name=patient_names.get(appt.patient_uuid),
                scheduled_at=appt.scheduled_at,
                noshow_probability=risk_probability,
                risk_color=risk_color,
                status=appt.status,
                sms_reminders_sent=appt.sms_reminders_sent,
            )
        )

    return predictions


@router.post("/no-show/reminders/dispatch", response_model=SMSDispatchSummary)
async def dispatch_noshow_sms_reminders(
    doctor_uuid: uuid.UUID = Query(...),
    date: DateType | None = Query(default=None),  # YYYY-MM-DD
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(require_secretary),
):
    """
    POST /api/v1/predictions/no-show/reminders/dispatch

    Triggers smart SMS reminders dispatch for appointments of one doctor/day.
    Rules applied:
    - send additional reminder only if probability > 30%
    - cap strict max to 2 reminders per appointment
    - always respect patient sms_opt_out preference
    """
    result = await db.execute(_build_doctor_appointments_query(doctor_uuid, date))
    appointments = result.scalars().all()

    dispatch_results = await dispatch_smart_sms_reminders(db, appointments)
    items = [
        SMSDispatchItem(
            appointment_uuid=item.appointment_uuid,
            risk_probability=item.risk_probability,
            sent=item.sent,
            reason=item.reason,
            sms_reminders_sent=item.sms_reminders_sent,
        )
        for item in dispatch_results
    ]

    sent_count = sum(1 for item in items if item.sent)
    return SMSDispatchSummary(
        total_candidates=len(items),
        sent=sent_count,
        skipped=len(items) - sent_count,
        items=items,
    )


class NoShowFeedbackRequest(BaseModel):
    outcome: Literal["presented", "no_show"]


class NoShowFeedbackResponse(BaseModel):
    id: uuid.UUID
    appointment_uuid: uuid.UUID
    outcome: str
    created_at: datetime
    updated_predictions: int = 0

    model_config = {"from_attributes": True}


async def _repredict_patient_future_appointments(
    db: AsyncSession,
    patient_uuid: uuid.UUID,
    previous_noshows: int,
) -> int:
    """Re-run no-show predictions for all future pending appointments of a patient.

    Returns the number of appointments whose probability was updated.
    """
    now = datetime.now(timezone.utc)

    # Fetch future non-terminal appointments for this patient
    result = await db.execute(
        select(Appointment).where(
            Appointment.patient_uuid == patient_uuid,
            Appointment.scheduled_at > now,
            Appointment.status.in_(["PENDING", "CONFIRMED"]),
        )
    )
    future_appointments = result.scalars().all()
    if not future_appointments:
        return 0

    # Fetch patient demographics for feature building
    patient_row = await db.execute(
        select(Patient).where(Patient.patient_uuid == patient_uuid)
    )
    patient = patient_row.scalar_one_or_none()
    if patient is None:
        return 0

    try:
        predictor = NoShowPredictor()
    except Exception:
        logger.warning("noshow_predictor_unavailable — skipping re-prediction")
        return 0

    updated = 0
    for appt in future_appointments:
        try:
            features = build_appointment_features(
                patient=patient,
                appointment=appt,
                previous_noshows=previous_noshows,
                now=now,
            )
            prediction = predictor.predict(features)
            appt.noshow_probability = prediction["noshow_probability"]
            appt.noshow_model_ver = prediction.get("model_version")
            updated += 1
        except (ModelNotReadyError, FeatureValidationError) as exc:
            logger.warning(
                "noshow_repredict_skip appt=%s reason=%s", appt.appointment_uuid, exc
            )

    if updated:
        await db.flush()

    return updated


@router.post(
    "/no-show/{appointment_uuid}/feedback",
    response_model=NoShowFeedbackResponse,
)
async def submit_noshow_feedback(
    appointment_uuid: uuid.UUID,
    body: NoShowFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("doctor", "secretary", "admin")),
):
    result = await db.execute(
        select(Appointment).where(Appointment.appointment_uuid == appointment_uuid)
    )
    appt = result.scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    # 1. Update appointment status based on feedback
    appt.status = "COMPLETED" if body.outcome == "presented" else "NO_SHOW"

    # 2. Save feedback record
    feedback = NoShowFeedback(
        appointment_uuid=appointment_uuid,
        outcome=body.outcome,
        recorded_by=uuid.UUID(current_user.sub),
    )
    db.add(feedback)
    await db.flush()

    # 3. Count total no-shows for this patient (ML feature: previous_noshows)
    count_result = await db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.patient_uuid == appt.patient_uuid,
            Appointment.status == "NO_SHOW",
        )
    )
    total_noshows = count_result.scalar() or 0

    # 4. Re-predict future appointments for this patient with updated history
    updated_count = await _repredict_patient_future_appointments(
        db, appt.patient_uuid, total_noshows
    )

    logger.info(
        "feedback_ml_loop patient=%s outcome=%s noshows=%d repredicted=%d",
        appt.patient_uuid, body.outcome, total_noshows, updated_count,
    )

    resp = NoShowFeedbackResponse.model_validate(feedback)
    resp.updated_predictions = updated_count
    return resp
