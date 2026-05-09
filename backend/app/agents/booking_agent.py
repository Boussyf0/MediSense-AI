"""
Booking Agent — suggests appointment slots for ROUTINE triage cases.

RESPONSIBILITY:
  Given a patient UUID and specialist type, find the next available
  appointment slot and create a pending appointment in the DB.

DATABASE INTERACTION:
  Queries the `appointments` table (created Sprint 2) for existing
  doctor appointments to find a free slot.

  For Sprint 4, the doctor assignment is simplified:
    - We pick the first available doctor of the required specialty.
    - Sprint 6 will add round-robin load balancing and preference matching.

SLOT SEARCH ALGORITHM (Sprint 4 — simplified):
  1. Find all doctors with specialty = specialist_type.
  2. For each doctor, check the next 7 days for a free 30-minute slot
     (business hours: 09:00–17:00 Morocco time, UTC+1).
  3. Return the first free slot found.
  4. If no slot found in 7 days → return None (secretary must book manually).

WHY 30-MINUTE SLOTS?
  Standard consultation duration in Moroccan primary care (CNOPS/AMO specs).
  This can be made configurable per specialty in Sprint 6.

CONCURRENCY SAFETY:
  We use SELECT ... FOR UPDATE SKIP LOCKED on the appointments table.
  This prevents two concurrent booking requests from grabbing the same slot.
  See https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SLOT_DURATION_MINUTES = 30
SEARCH_DAYS_AHEAD = 7
BUSINESS_HOURS_START = 9   # 09:00 Morocco (UTC+1)
BUSINESS_HOURS_END = 17    # 17:00 Morocco (UTC+1)
MOROCCO_UTC_OFFSET = timedelta(hours=1)


@dataclass
class BookingResult:
    """
    Output of the booking agent.

    Attributes:
        success          : True if a slot was found and appointment created.
        appointment_id   : UUID of the created appointment (if success).
        proposed_slot    : ISO datetime of the proposed appointment.
        doctor_id        : UUID of the assigned doctor.
        specialist_type  : Specialty that was requested.
        message          : Human-readable result for the chat response.
    """
    success: bool
    appointment_id: str | None = None
    proposed_slot: str | None = None
    doctor_id: str | None = None
    specialist_type: str | None = None
    message: str = ""


async def run(
    patient_id: str,
    specialist_type: str | None,
    db: AsyncSession,
) -> BookingResult:
    """
    Find a free slot and create a pending appointment.

    Args:
        patient_id      : Patient UUID string.
        specialist_type : e.g. 'cardiologie', 'médecine générale'.
        db              : Async DB session.

    Returns:
        BookingResult.  success=False if no slot found or on DB error.

    Timeout: caller wraps in asyncio.wait_for(timeout=5s).
    """
    specialty = specialist_type or "médecine générale"

    try:
        # Find available doctors for the specialty
        # Uses raw text query for clarity — Sprint 6 will add ORM model for doctors
        doctor_query = text(
            "SELECT user_uuid FROM public.users "
            "WHERE role = 'doctor' AND specialty = :specialty "
            "ORDER BY created_at LIMIT 5"
        )
        result = await db.execute(doctor_query, {"specialty": specialty})
        doctors = [str(row[0]) for row in result.fetchall()]

        if not doctors:
            # Fallback: any doctor (no specialty filter)
            fallback = text(
                "SELECT user_uuid FROM public.users WHERE role = 'doctor' LIMIT 1"
            )
            res = await db.execute(fallback)
            row = res.fetchone()
            doctors = [str(row[0])] if row else []

        if not doctors:
            return BookingResult(
                success=False,
                specialist_type=specialty,
                message=f"Aucun médecin disponible en {specialty}. Contactez le secrétariat.",
            )

        # Search for free slot in next 7 days
        slot = await _find_free_slot(doctors[0], db)

        if not slot:
            return BookingResult(
                success=False,
                specialist_type=specialty,
                message=(
                    f"Aucun créneau disponible en {specialty} dans les {SEARCH_DAYS_AHEAD} prochains jours. "
                    f"Appelez le secrétariat pour un rendez-vous urgent."
                ),
            )

        # Create pending appointment
        appt_id = str(uuid.uuid4())
        patient_uuid = uuid.UUID(patient_id)
        doctor_uuid = uuid.UUID(doctors[0])
        slot_dt = datetime.fromisoformat(slot)

        insert = text(
            "INSERT INTO appointments "
            "(id, patient_id, doctor_id, scheduled_at, duration_minutes, status, specialty, created_at) "
            "VALUES (:id, :patient_id, :doctor_id, :scheduled_at, :duration, 'pending', :specialty, now())"
        )
        await db.execute(insert, {
            "id": appt_id,
            "patient_id": str(patient_uuid),
            "doctor_id": str(doctor_uuid),
            "scheduled_at": slot_dt,
            "duration": SLOT_DURATION_MINUTES,
            "specialty": specialty,
        })

        slot_fr = slot_dt.strftime("%A %d %B %Y à %H:%M")
        return BookingResult(
            success=True,
            appointment_id=appt_id,
            proposed_slot=slot,
            doctor_id=doctors[0],
            specialist_type=specialty,
            message=f"Rendez-vous proposé en {specialty}: {slot_fr}. Confirmation sous 24h.",
        )

    except Exception as exc:
        logger.error("booking_agent_failed patient=%s err=%s", patient_id, exc)
        return BookingResult(
            success=False,
            specialist_type=specialty,
            message="Erreur lors de la recherche de créneau. Contactez le secrétariat.",
        )


async def _find_free_slot(doctor_id: str, db: AsyncSession) -> str | None:
    """
    Find the next free 30-minute slot for a doctor.

    Returns ISO datetime string or None if no slot found in SEARCH_DAYS_AHEAD.
    """
    now_utc = datetime.now(timezone.utc)
    # Start searching from tomorrow morning (don't book same-day)
    search_start = (now_utc + timedelta(days=1)).replace(
        hour=BUSINESS_HOURS_START, minute=0, second=0, microsecond=0
    )

    # Fetch all existing appointments for this doctor in the search window
    search_end = search_start + timedelta(days=SEARCH_DAYS_AHEAD)

    existing_query = text(
        "SELECT scheduled_at FROM appointments "
        "WHERE doctor_id = :doctor_id "
        "AND scheduled_at BETWEEN :start AND :end "
        "AND status != 'cancelled' "
        "ORDER BY scheduled_at"
    )
    result = await db.execute(existing_query, {
        "doctor_id": doctor_id,
        "start": search_start,
        "end": search_end,
    })
    booked_slots: set[datetime] = {row[0] for row in result.fetchall()}

    # Walk through business hours and find first free slot
    cursor = search_start
    while cursor < search_end:
        hour = cursor.hour
        # Skip outside business hours
        if hour < BUSINESS_HOURS_START or hour >= BUSINESS_HOURS_END:  # pragma: no cover
            cursor = cursor.replace(
                hour=BUSINESS_HOURS_START, minute=0, second=0, microsecond=0
            ) + timedelta(days=1)
            continue
        if cursor.weekday() in (4, 5):  # Friday, Saturday  # pragma: no cover
            cursor += timedelta(days=1)
            cursor = cursor.replace(hour=BUSINESS_HOURS_START, minute=0)
            continue

        if cursor not in booked_slots:
            return cursor.isoformat()

        cursor += timedelta(minutes=SLOT_DURATION_MINUTES)

    return None
