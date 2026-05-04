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

router = APIRouter(prefix="/predictions", tags=["ml"])


class AppointmentPrediction(BaseModel):
    appointment_uuid: uuid.UUID
    patient_uuid: uuid.UUID
    scheduled_at: datetime
    noshow_probability: float | None
    risk_color: str
    status: str

@router.get("/no-show/batch", response_model=List[AppointmentPrediction])
async def get_noshow_predictions_batch(
    doctor_uuid: uuid.UUID = Query(...),
    date: DateType | None = Query(default=None),  # YYYY-MM-DD
    db: AsyncSession = Depends(get_db),
    _current_user: TokenPayload = Depends(require_secretary),
):
    """
    GET /api/v1/predictions/no-show/batch
    Returns a list of appointments for the Smart Agenda with no-show risks.
    Color coding: green < 20%, orange 20-40%, red > 40%.
    """
    query = select(Appointment).where(Appointment.doctor_uuid == doctor_uuid)
    
    if date is not None:
        start_of_day = datetime.combine(date, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(date, time.max, tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_at.between(start_of_day, end_of_day))
        
    result = await db.execute(query)
    appointments = result.scalars().all()
    
    predictions = []
    for appt in appointments:
        prob = appt.noshow_probability or 0.0
            
        predictions.append(AppointmentPrediction(
            appointment_uuid=appt.appointment_uuid,
            patient_uuid=appt.patient_uuid,
            scheduled_at=appt.scheduled_at,
            noshow_probability=appt.noshow_probability,
            risk_color=get_risk_color(prob),
            status=appt.status
        ))
        
    return predictions
