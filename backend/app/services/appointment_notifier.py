"""Notify the parties of an appointment-lifecycle event — durable + push.

Each event writes a Notification row per recipient (survives an offline/logged-out
ACCOUNT — read from the inbox on next login) AND fires a best-effort FCM push to
their devices (survives an offline APP via FCM store-and-forward). The row is the
source of truth; push is best-effort and never breaks the triggering request.

Recipients = the patient + the assigned doctor + all secretaries, minus whoever
performed the action (no point notifying yourself).
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.appointment import Appointment
from app.db.models.device_token import DeviceToken
from app.db.models.notification import Notification
from app.db.models.user import User, UserRole
from app.services.fcm_service import send_to_token

logger = logging.getLogger(__name__)

# event key -> (title, body template). French, patient-facing wording.
_MESSAGES: dict[str, tuple[str, str]] = {
    "booked":    ("Nouveau rendez-vous",   "Un rendez-vous a été planifié pour le {when}."),
    "confirmed": ("Rendez-vous confirmé",  "Le rendez-vous du {when} est confirmé."),
    "cancelled": ("Rendez-vous annulé",    "Le rendez-vous du {when} a été annulé."),
    "completed": ("Consultation terminée", "La consultation du {when} est terminée."),
    "no_show":   ("Absence constatée",     "Absence constatée au rendez-vous du {when}."),
}


async def notify_appointment_event(
    db: AsyncSession,
    appt: Appointment,
    event: str,
    actor_uuid: uuid.UUID,
) -> None:
    """Persist a notification per recipient and push best-effort via FCM."""
    title, template = _MESSAGES[event]
    when = appt.scheduled_at.strftime("%d/%m/%Y %H:%M")
    body = template.format(when=when)

    recipients: set[uuid.UUID] = {appt.patient_uuid}
    if appt.doctor_uuid is not None:
        recipients.add(appt.doctor_uuid)
    secretary_ids = (
        await db.execute(select(User.user_uuid).where(User.role == UserRole.SECRETARY))
    ).scalars().all()
    recipients.update(secretary_ids)
    recipients.discard(actor_uuid)
    # Keep only recipients that have a user account — a pseudonymized patient
    # (Patient row without a login User) cannot receive notifications, and the
    # Notification FK to users would otherwise fail.
    if recipients:
        existing = set(
            (
                await db.execute(select(User.user_uuid).where(User.user_uuid.in_(recipients)))
            ).scalars().all()
        )
        recipients &= existing
    if not recipients:
        return

    ntype = f"appointment_{event}"
    for uid in recipients:
        db.add(Notification(
            user_uuid=uid, type=ntype, title=title, body=body,
            appointment_uuid=appt.appointment_uuid,
        ))
    await db.flush()

    # Best-effort push — FCM store-and-forwards to offline apps. Never raise.
    tokens = (
        await db.execute(select(DeviceToken.token).where(DeviceToken.user_uuid.in_(recipients)))
    ).scalars().all()
    data = {"type": ntype, "appointment_uuid": str(appt.appointment_uuid)}
    for tok in tokens:
        try:
            await send_to_token(tok, title, body, data)
        except Exception as exc:  # pragma: no cover — push transport is best-effort
            logger.warning("appointment push failed: %s", exc)
