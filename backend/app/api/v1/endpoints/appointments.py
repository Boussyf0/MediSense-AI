"""
Patient-facing appointments endpoint — used by the Flutter mobile Agenda page.

Different from /predictions/no-show/batch (doctor/secretary triage view):
- Auth: any authenticated user; if role == "patient", filters to their own
  appointments. Staff users get filtered by doctor_uuid = self.
- Joins users table for human-readable doctor name.
- Maps noshow_probability → risk_color so the mobile UI can render chips
  without a second round-trip to the predictor.
"""
import uuid
from datetime import date as DateType, datetime, time, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, get_current_user
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.services.noshow_predictor import get_risk_color

router = APIRouter(prefix="/appointments", tags=["appointments"])


class AppointmentItem(BaseModel):
    appointment_uuid: uuid.UUID
    scheduled_at: datetime
    appointment_time: str
    appointment_type: str
    doctor_name: str
    status: str
    noshow_probability: float | None
    risk_color: str | None


class AppointmentCreate(BaseModel):
    patient_uuid: uuid.UUID
    doctor_uuid: uuid.UUID
    scheduled_at: datetime
    duration_minutes: int = Field(default=20, ge=5, le=240)


class AppointmentCreated(BaseModel):
    appointment_uuid: uuid.UUID
    patient_uuid: uuid.UUID
    doctor_uuid: uuid.UUID
    scheduled_at: datetime
    duration_minutes: int
    status: str
    doctor_name: str


@router.get("", response_model=List[AppointmentItem])
async def list_my_appointments(
    date: DateType | None = Query(default=None, description="Filter by day (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    GET /api/v1/appointments?date=YYYY-MM-DD

    Lists appointments scoped to the caller:
    - patient → their own appointments
    - doctor → appointments they are the practitioner for
    - secretary/admin → unscoped by user, but date filter still applies
    """
    user_uuid = uuid.UUID(current_user.sub)
    query = (
        select(Appointment, User)
        .join(User, User.user_uuid == Appointment.doctor_uuid)
    )
    if current_user.role == "patient":
        query = query.where(Appointment.patient_uuid == user_uuid)
    elif current_user.role == "doctor":
        query = query.where(Appointment.doctor_uuid == user_uuid)
    # secretary/admin see all

    if date is not None:
        start_of_day = datetime.combine(date, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(date, time.max, tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_at.between(start_of_day, end_of_day))

    query = query.order_by(Appointment.scheduled_at.asc())
    rows = (await db.execute(query)).all()

    items: List[AppointmentItem] = []
    for appt, doctor in rows:
        doctor_label = " ".join(
            part for part in [doctor.first_name, doctor.last_name] if part
        ) or doctor.email
        items.append(
            AppointmentItem(
                appointment_uuid=appt.appointment_uuid,
                scheduled_at=appt.scheduled_at,
                appointment_time=appt.scheduled_at.strftime("%H:%M"),
                appointment_type="Consultation",
                doctor_name=f"Dr. {doctor_label}",
                status=appt.status,
                noshow_probability=appt.noshow_probability,
                risk_color=(
                    get_risk_color(appt.noshow_probability)
                    if appt.noshow_probability is not None
                    else None
                ),
            )
        )
    return items


@router.post(
    "",
    response_model=AppointmentCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Book a new appointment",
)
async def create_appointment(
    body: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(get_current_user),
):
    """
    POST /api/v1/appointments — patient-facing booking.

    Rules:
      - patient role can only book for themselves (patient_uuid == self)
      - doctor/secretary/admin can book for any patient
      - scheduled_at must be in the future (UTC)
      - doctor_uuid must point to an active user with role=doctor
      - patient_uuid must point to an active patient
      - 409 if the doctor already has an appointment at the exact scheduled_at
    """
    caller_uuid = uuid.UUID(current_user.sub)

    if current_user.role == "patient" and body.patient_uuid != caller_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Patients can only book appointments for themselves",
        )

    scheduled_at = body.scheduled_at
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    if scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scheduled_at must be in the future",
        )

    doctor = (
        await db.execute(
            select(User).where(
                User.user_uuid == body.doctor_uuid,
                User.role == UserRole.DOCTOR,
                User.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found or inactive",
        )

    patient = (
        await db.execute(
            select(Patient).where(
                Patient.patient_uuid == body.patient_uuid,
                Patient.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or inactive",
        )

    clash = (
        await db.execute(
            select(Appointment.appointment_uuid).where(
                Appointment.doctor_uuid == body.doctor_uuid,
                Appointment.scheduled_at == scheduled_at,
            )
        )
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor already has an appointment at this exact time",
        )

    appt = Appointment(
        patient_uuid=body.patient_uuid,
        doctor_uuid=body.doctor_uuid,
        scheduled_at=scheduled_at,
        duration_minutes=body.duration_minutes,
        status="PENDING",
    )
    db.add(appt)
    await db.flush()

    doctor_label = " ".join(
        part for part in [doctor.first_name, doctor.last_name] if part
    ) or doctor.email

    return AppointmentCreated(
        appointment_uuid=appt.appointment_uuid,
        patient_uuid=appt.patient_uuid,
        doctor_uuid=appt.doctor_uuid,
        scheduled_at=appt.scheduled_at,
        duration_minutes=appt.duration_minutes,
        status=appt.status,
        doctor_name=f"Dr. {doctor_label}",
    )
