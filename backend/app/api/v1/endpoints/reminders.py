import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import TokenPayload, require_patient
from app.db.models.medication_reminder import MedicationReminder
from app.db.session import get_db
from app.schemas.reminders import ReminderCreate, ReminderOut, ReminderUpdate

router = APIRouter(prefix="/reminders", tags=["Reminders"])


def _to_out(r: MedicationReminder) -> ReminderOut:
    return ReminderOut(
        id=r.id,
        name=r.name,
        dosage=r.dosage,
        time=r.time_of_day,
        days_of_week=list(r.days_of_week or []),
        enabled=r.enabled,
        created_at=r.created_at,
    )


@router.get("", response_model=list[ReminderOut])
async def list_reminders(
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> list[ReminderOut]:
    patient_uuid = uuid.UUID(current_user.sub)
    result = await db.execute(
        select(MedicationReminder)
        .where(MedicationReminder.patient_uuid == patient_uuid)
        .order_by(MedicationReminder.created_at.asc())
    )
    rows = result.scalars().all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=ReminderOut, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    body: ReminderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> ReminderOut:
    patient_uuid = uuid.UUID(current_user.sub)
    reminder = MedicationReminder(
        patient_uuid=patient_uuid,
        name=body.name,
        dosage=body.dosage,
        time_of_day=body.time,
        days_of_week=body.days_of_week,
        enabled=True,
    )
    db.add(reminder)
    await db.flush()
    return _to_out(reminder)


@router.patch("/{reminder_uuid}", response_model=ReminderOut)
async def update_reminder(
    reminder_uuid: uuid.UUID,
    body: ReminderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> ReminderOut:
    patient_uuid = uuid.UUID(current_user.sub)
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_uuid,
            MedicationReminder.patient_uuid == patient_uuid,
        )
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    if body.name is not None:
        reminder.name = body.name
    if body.dosage is not None:
        reminder.dosage = body.dosage
    if body.time is not None:
        reminder.time_of_day = body.time
    if body.days_of_week is not None:
        reminder.days_of_week = body.days_of_week
    if body.enabled is not None:
        reminder.enabled = body.enabled

    await db.flush()
    return _to_out(reminder)


@router.delete("/{reminder_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    reminder_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_patient),
) -> Response:
    patient_uuid = uuid.UUID(current_user.sub)
    result = await db.execute(
        select(MedicationReminder).where(
            MedicationReminder.id == reminder_uuid,
            MedicationReminder.patient_uuid == patient_uuid,
        )
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    await db.delete(reminder)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
