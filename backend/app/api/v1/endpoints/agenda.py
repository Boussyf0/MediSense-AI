import uuid
from datetime import date as DateType, datetime, time, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_secretary
from app.db.models.appointment import Appointment
from app.db.session import get_db
from app.services.noshow_predictor import get_risk_color
from app.services.sms_reminder import dispatch_smart_sms_reminders

router = APIRouter(prefix="/predictions", tags=["ml"])


class AppointmentPrediction(BaseModel):
    appointment_uuid: uuid.UUID
    patient_uuid: uuid.UUID
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
        default=True,
        description=(
            "If true, automatically dispatch one additional reminder SMS for "
            "appointments with predicted no-show probability > 30%, while "
            "respecting opt-out and max-2 reminders."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(require_secretary),
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
