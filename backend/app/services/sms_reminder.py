from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import httpx
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SMSReminderDispatchResult:
    appointment_uuid: uuid.UUID
    risk_probability: float
    sent: bool
    reason: str
    sms_reminders_sent: int


def _mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) <= 2:
        return "***"
    return f"***{digits[-2:]}"


def _build_sms_message(appointment: Appointment, risk_probability: float) -> str:
    scheduled_utc = appointment.scheduled_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
    risk_percent = round(risk_probability * 100)
    return (
        f"Rappel MediSense: votre RDV est prévu le {scheduled_utc} UTC. "
        f"Votre profil indique un risque d'oubli ({risk_percent}%). "
        "Merci de confirmer votre présence."
    )


async def _get_patient_phone_number(db: AsyncSession, patient_uuid: uuid.UUID) -> str | None:  # pragma: no cover
    query = text(
        "SELECT pgp_sym_decrypt(phone_enc, :key)::text AS phone "
        "FROM secure.patients_identity "
        "WHERE patient_uuid = :patient_uuid"
    )
    result = await db.execute(
        query,
        {"key": settings.PGCRYPTO_KEY, "patient_uuid": str(patient_uuid)},
    )
    phone = result.scalar_one_or_none()
    if not phone:
        return None
    return str(phone).strip()


async def _reserve_sms_slot(
    db: AsyncSession,
    appointment_uuid: uuid.UUID,
    max_count: int,
) -> int | None:
    stmt = (
        update(Appointment)
        .where(
            Appointment.appointment_uuid == appointment_uuid,
            Appointment.sms_reminders_sent < max_count,
        )
        .values(sms_reminders_sent=Appointment.sms_reminders_sent + 1)
        .returning(Appointment.sms_reminders_sent)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _release_sms_slot(db: AsyncSession, appointment_uuid: uuid.UUID) -> None:
    stmt = (
        update(Appointment)
        .where(
            Appointment.appointment_uuid == appointment_uuid,
            Appointment.sms_reminders_sent > 0,
        )
        .values(sms_reminders_sent=Appointment.sms_reminders_sent - 1)
    )
    await db.execute(stmt)


async def _mark_sms_sent_now(db: AsyncSession, appointment_uuid: uuid.UUID) -> None:
    stmt = (
        update(Appointment)
        .where(Appointment.appointment_uuid == appointment_uuid)
        .values(last_sms_reminder_at=datetime.now(timezone.utc))
    )
    await db.execute(stmt)


async def _send_sms(  # pragma: no cover
    phone_number: str,
    message: str,
    appointment_uuid: uuid.UUID,
    patient_uuid: uuid.UUID,
) -> str:
    if not settings.SMS_WEBHOOK_URL:
        return f"mock-{uuid.uuid4()}"

    payload = {
        "to": phone_number,
        "message": message,
        "metadata": {
            "appointment_uuid": str(appointment_uuid),
            "patient_uuid": str(patient_uuid),
        },
    }
    headers = {"Content-Type": "application/json"}
    if settings.SMS_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {settings.SMS_WEBHOOK_TOKEN}"

    async with httpx.AsyncClient(timeout=settings.SMS_PROVIDER_TIMEOUT_SECONDS) as client:
        response = await client.post(
            settings.SMS_WEBHOOK_URL,
            json=payload,
            headers=headers,
        )

    if response.status_code >= 400:
        raise RuntimeError(f"SMS provider error HTTP {response.status_code}")

    data = {}
    if response.content:
        try:
            data = response.json()
        except ValueError:
            data = {}
    message_id = data.get("message_id")
    return str(message_id) if message_id else f"http-{response.status_code}"


async def dispatch_smart_sms_reminders(
    db: AsyncSession,
    appointments: Sequence[Appointment],
) -> list[SMSReminderDispatchResult]:
    results: list[SMSReminderDispatchResult] = []

    for appointment in appointments:
        probability = float(appointment.noshow_probability or 0.0)
        current_count = int(appointment.sms_reminders_sent or 0)

        if probability <= settings.SMS_REMINDER_THRESHOLD:
            results.append(
                SMSReminderDispatchResult(
                    appointment_uuid=appointment.appointment_uuid,
                    risk_probability=probability,
                    sent=False,
                    reason="below_threshold",
                    sms_reminders_sent=current_count,
                )
            )
            continue

        if current_count >= settings.SMS_REMINDER_MAX_COUNT:
            results.append(
                SMSReminderDispatchResult(
                    appointment_uuid=appointment.appointment_uuid,
                    risk_probability=probability,
                    sent=False,
                    reason="max_reminders_reached",
                    sms_reminders_sent=current_count,
                )
            )
            continue

        patient_stmt = select(Patient).where(Patient.patient_uuid == appointment.patient_uuid)
        patient_result = await db.execute(patient_stmt)
        patient = patient_result.scalar_one_or_none()
        if patient is None or not patient.is_active:
            results.append(
                SMSReminderDispatchResult(
                    appointment_uuid=appointment.appointment_uuid,
                    risk_probability=probability,
                    sent=False,
                    reason="patient_inactive_or_missing",
                    sms_reminders_sent=current_count,
                )
            )
            continue

        if patient.sms_opt_out:
            results.append(
                SMSReminderDispatchResult(
                    appointment_uuid=appointment.appointment_uuid,
                    risk_probability=probability,
                    sent=False,
                    reason="opt_out",
                    sms_reminders_sent=current_count,
                )
            )
            continue

        phone_number = await _get_patient_phone_number(db, appointment.patient_uuid)
        if not phone_number:
            results.append(
                SMSReminderDispatchResult(
                    appointment_uuid=appointment.appointment_uuid,
                    risk_probability=probability,
                    sent=False,
                    reason="missing_phone",
                    sms_reminders_sent=current_count,
                )
            )
            continue

        reserved_count = await _reserve_sms_slot(
            db,
            appointment.appointment_uuid,
            settings.SMS_REMINDER_MAX_COUNT,
        )
        if reserved_count is None:
            results.append(
                SMSReminderDispatchResult(
                    appointment_uuid=appointment.appointment_uuid,
                    risk_probability=probability,
                    sent=False,
                    reason="max_reminders_reached",
                    sms_reminders_sent=current_count,
                )
            )
            continue

        sms_message = _build_sms_message(appointment, probability)
        try:
            message_id = await _send_sms(
                phone_number=phone_number,
                message=sms_message,
                appointment_uuid=appointment.appointment_uuid,
                patient_uuid=appointment.patient_uuid,
            )
        except (httpx.HTTPError, RuntimeError) as exc:
            await _release_sms_slot(db, appointment.appointment_uuid)
            logger.warning(
                "sms_send_failed appointment=%s patient=%s phone=%s err=%s",
                appointment.appointment_uuid,
                appointment.patient_uuid,
                _mask_phone(phone_number),
                exc,
            )
            results.append(
                SMSReminderDispatchResult(
                    appointment_uuid=appointment.appointment_uuid,
                    risk_probability=probability,
                    sent=False,
                    reason="send_failed",
                    sms_reminders_sent=max(reserved_count - 1, 0),
                )
            )
            continue

        logger.info(
            "sms_sent appointment=%s patient=%s phone=%s count=%s message_id=%s",
            appointment.appointment_uuid,
            appointment.patient_uuid,
            _mask_phone(phone_number),
            reserved_count,
            message_id,
        )
        await _mark_sms_sent_now(db, appointment.appointment_uuid)
        results.append(
            SMSReminderDispatchResult(
                appointment_uuid=appointment.appointment_uuid,
                risk_probability=probability,
                sent=True,
                reason="sent",
                sms_reminders_sent=reserved_count,
            )
        )

    return results
