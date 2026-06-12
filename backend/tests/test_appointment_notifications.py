"""Appointment confirm transition + durable notification inbox (offline-safe)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.notification import Notification
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole


def auth_for(subject: uuid.UUID, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=str(subject), role=role)}"}


async def _seed(test_db, *, patient_uuid, doctor_uuid, secretary_uuid=None, status="PENDING"):
    test_db.add(User(user_uuid=patient_uuid, email=f"p-{patient_uuid}@m.ai",
                     hashed_password="x", role=UserRole.PATIENT, is_active=True))
    test_db.add(Patient(patient_uuid=patient_uuid, consent_iot=False, consent_nlp=False,
                        consent_sharing=False, sms_opt_out=False, birth_year=1990, sex="M",
                        city_code="40000", chronic_conditions=[]))
    test_db.add(User(user_uuid=doctor_uuid, email=f"d-{doctor_uuid}@m.ai",
                     hashed_password="x", role=UserRole.DOCTOR, first_name="Doc",
                     last_name="Tor", is_active=True))
    if secretary_uuid:
        test_db.add(User(user_uuid=secretary_uuid, email=f"s-{secretary_uuid}@m.ai",
                         hashed_password="x", role=UserRole.SECRETARY, is_active=True))
    await test_db.flush()  # persist users + patient before FK-referencing them
    appt = Appointment(patient_uuid=patient_uuid, doctor_uuid=doctor_uuid,
                       scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
                       duration_minutes=30, status=status)
    test_db.add(appt)
    await test_db.flush()
    return appt


# ── PATCH /appointments/{id}/confirm ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_appointment_staff_ok(client, test_db):
    pid, did, sid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    appt = await _seed(test_db, patient_uuid=pid, doctor_uuid=did, secretary_uuid=sid)
    r = await client.patch(f"/api/v1/appointments/{appt.appointment_uuid}/confirm",
                           headers=auth_for(sid, "secretary"))
    assert r.status_code == 200
    assert r.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_confirm_appointment_patient_forbidden(client, test_db):
    pid, did = uuid.uuid4(), uuid.uuid4()
    appt = await _seed(test_db, patient_uuid=pid, doctor_uuid=did)
    r = await client.patch(f"/api/v1/appointments/{appt.appointment_uuid}/confirm",
                           headers=auth_for(pid, "patient"))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_confirm_appointment_non_pending_409(client, test_db):
    pid, did = uuid.uuid4(), uuid.uuid4()
    appt = await _seed(test_db, patient_uuid=pid, doctor_uuid=did, status="CONFIRMED")
    r = await client.patch(f"/api/v1/appointments/{appt.appointment_uuid}/confirm",
                           headers=auth_for(did, "doctor"))
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_confirm_appointment_not_found_404(client, test_db):
    r = await client.patch(f"/api/v1/appointments/{uuid.uuid4()}/confirm",
                           headers=auth_for(uuid.uuid4(), "doctor"))
    assert r.status_code == 404


# ── Notification side-effect + inbox ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_creates_durable_notification_for_patient(client, test_db):
    pid, did = uuid.uuid4(), uuid.uuid4()
    appt = await _seed(test_db, patient_uuid=pid, doctor_uuid=did)
    await client.patch(f"/api/v1/appointments/{appt.appointment_uuid}/confirm",
                       headers=auth_for(did, "doctor"))
    notifs = (
        await test_db.execute(select(Notification).where(Notification.user_uuid == pid))
    ).scalars().all()
    assert any(n.type == "appointment_confirmed" for n in notifs)


@pytest.mark.asyncio
async def test_list_notifications_requires_auth(client):
    r = await client.get("/api/v1/notifications")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_and_mark_read(client, test_db):
    pid, did = uuid.uuid4(), uuid.uuid4()
    appt = await _seed(test_db, patient_uuid=pid, doctor_uuid=did)
    await client.patch(f"/api/v1/appointments/{appt.appointment_uuid}/confirm",
                       headers=auth_for(did, "doctor"))

    r = await client.get("/api/v1/notifications", headers=auth_for(pid, "patient"))
    assert r.status_code == 200
    data = r.json()
    assert data["unread_count"] >= 1
    nid = data["items"][0]["id"]

    r2 = await client.post(f"/api/v1/notifications/{nid}/read", headers=auth_for(pid, "patient"))
    assert r2.status_code == 204

    r3 = await client.get("/api/v1/notifications?unread_only=true", headers=auth_for(pid, "patient"))
    assert all(item["id"] != nid for item in r3.json()["items"])


@pytest.mark.asyncio
async def test_confirm_attempts_push_to_registered_device(client, test_db, monkeypatch):
    from app.db.models.device_token import DeviceToken

    pid, did = uuid.uuid4(), uuid.uuid4()
    appt = await _seed(test_db, patient_uuid=pid, doctor_uuid=did)
    test_db.add(DeviceToken(user_uuid=pid, token="tok-123", platform="android"))
    await test_db.flush()

    sent: list[str] = []

    async def fake_send(token, title, body, data=None):
        sent.append(token)
        return True

    monkeypatch.setattr("app.services.appointment_notifier.send_to_token", fake_send)
    await client.patch(f"/api/v1/appointments/{appt.appointment_uuid}/confirm",
                       headers=auth_for(did, "doctor"))
    assert "tok-123" in sent  # push attempted to the patient's device


@pytest.mark.asyncio
async def test_mark_read_not_found_404(client, test_db):
    pid = uuid.uuid4()
    test_db.add(User(user_uuid=pid, email=f"p-{pid}@m.ai", hashed_password="x",
                     role=UserRole.PATIENT, is_active=True))
    await test_db.flush()
    r = await client.post(f"/api/v1/notifications/{uuid.uuid4()}/read",
                          headers=auth_for(pid, "patient"))
    assert r.status_code == 404
