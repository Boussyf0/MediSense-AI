"""Tests for GET /notifications/inbox — polling fallback for FCM."""
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.sms_reminder_log import SmsReminderLog
from app.db.models.user import User, UserRole


def _patient_auth(patient_uuid: uuid.UUID) -> dict[str, str]:
    token = create_access_token(subject=str(patient_uuid), role="patient")
    return {"Authorization": f"Bearer {token}"}


async def _seed_patient_with_user(test_db) -> uuid.UUID:
    pid = uuid.uuid4()
    test_db.add(User(
        user_uuid=pid,
        email=f"p-{pid}@medisense.ai",
        hashed_password="hashed",
        role=UserRole.PATIENT,
        first_name="Pa",
        last_name="Ti",
        is_active=True,
    ))
    test_db.add(Patient(
        patient_uuid=pid,
        consent_iot=False, consent_nlp=False, consent_sharing=False,
        sms_opt_out=False, birth_year=1990, sex="F",
        city_code="20000", chronic_conditions=[],
    ))
    await test_db.flush()
    return pid


async def _seed_appt_with_sent_log(test_db, patient_uuid: uuid.UUID, sent_at: datetime) -> uuid.UUID:
    doctor_uuid = uuid.uuid4()
    test_db.add(User(
        user_uuid=doctor_uuid,
        email=f"d-{doctor_uuid}@medisense.ai",
        hashed_password="hashed",
        role=UserRole.DOCTOR,
        first_name="Doc", last_name="Tor", is_active=True,
    ))
    await test_db.flush()
    appt_uuid = uuid.uuid4()
    test_db.add(Appointment(
        appointment_uuid=appt_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
    ))
    await test_db.flush()
    test_db.add(SmsReminderLog(
        appointment_uuid=appt_uuid,
        task_type="sms_reminder",
        status="sent",
        scheduled_for=sent_at,
        scheduled_date=sent_at.date(),
    ))
    await test_db.flush()
    return appt_uuid


@pytest.mark.asyncio
async def test_inbox_requires_auth(client):
    """HTTPBearer returns 403 when Authorization header absent."""
    resp = await client.get("/api/v1/notifications/inbox")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_inbox_returns_sent_reminders_for_caller(client, test_db):
    pid = await _seed_patient_with_user(test_db)
    appt_uuid = await _seed_appt_with_sent_log(
        test_db, pid, datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    resp = await client.get("/api/v1/notifications/inbox", headers=_patient_auth(pid))
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["appointment_uuid"] == str(appt_uuid)
    assert items[0]["status"] == "sent"
    assert items[0]["title"] == "Rappel de rendez-vous"


@pytest.mark.asyncio
async def test_inbox_filters_other_patients(client, test_db):
    pid_a = await _seed_patient_with_user(test_db)
    pid_b = await _seed_patient_with_user(test_db)
    await _seed_appt_with_sent_log(test_db, pid_b, datetime.now(timezone.utc))
    resp = await client.get("/api/v1/notifications/inbox", headers=_patient_auth(pid_a))
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_inbox_since_filter(client, test_db):
    pid = await _seed_patient_with_user(test_db)
    now = datetime.now(timezone.utc)
    await _seed_appt_with_sent_log(test_db, pid, now - timedelta(hours=2))
    await _seed_appt_with_sent_log(test_db, pid, now)
    cutoff = quote((now - timedelta(hours=1)).isoformat())
    resp = await client.get(
        f"/api/v1/notifications/inbox?since={cutoff}",
        headers=_patient_auth(pid),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1


@pytest.mark.asyncio
async def test_inbox_excludes_non_sent_status(client, test_db):
    """skipped / failed / pending must not appear in inbox."""
    pid = await _seed_patient_with_user(test_db)
    doctor_uuid = uuid.uuid4()
    test_db.add(User(
        user_uuid=doctor_uuid, email=f"d-{doctor_uuid}@x.com",
        hashed_password="h", role=UserRole.DOCTOR,
        first_name="D", last_name="T", is_active=True,
    ))
    await test_db.flush()
    appt_uuid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    test_db.add(Appointment(
        appointment_uuid=appt_uuid, patient_uuid=pid, doctor_uuid=doctor_uuid,
        scheduled_at=now + timedelta(days=1), duration_minutes=20, status="PENDING",
    ))
    await test_db.flush()
    test_db.add(SmsReminderLog(
        appointment_uuid=appt_uuid, task_type="sms_reminder",
        status="skipped", scheduled_for=now, scheduled_date=now.date(),
    ))
    await test_db.flush()
    resp = await client.get("/api/v1/notifications/inbox", headers=_patient_auth(pid))
    assert resp.status_code == 200
    assert resp.json()["items"] == []
