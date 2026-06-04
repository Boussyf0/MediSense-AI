"""
Tests for notification endpoints — Sprint 7 (US-29).

Coverage: POST /notifications/register-token, GET /notifications/inbox,
DELETE /notifications/token/{token}.
"""
import uuid
from datetime import datetime, timezone

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.sms_reminder_log import SmsReminderLog
from app.db.models.user import User, UserRole


def auth(role: str, sub: str | None = None) -> dict[str, str]:
    token = create_access_token(subject=sub or str(uuid.uuid4()), role=role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_user(test_db, role: str = "patient") -> uuid.UUID:
    user_uuid = uuid.uuid4()
    user = User(
        user_uuid=user_uuid,
        email=f"{role}-{user_uuid}@test.ai",
        hashed_password="hashed",
        role=UserRole(role),
        first_name="Test",
        last_name="User",
        is_active=True,
    )
    test_db.add(user)
    await test_db.flush()
    return user_uuid


# ── POST /notifications/register-token ──────────────────────────────────────


async def test_register_token_no_auth(client):
    """No bearer → 403."""
    resp = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "a" * 20, "platform": "android"},
    )
    assert resp.status_code == 403


async def test_register_token_happy(client, test_db):
    """Register a new FCM token → 201 with token details."""
    user_uuid = await _seed_user(test_db)
    resp = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "fcm_token_12345678", "platform": "android"},
        headers=auth("patient", sub=str(user_uuid)),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["token"] == "fcm_token_12345678"
    assert data["platform"] == "android"


async def test_register_token_rebind(client, test_db):
    """Re-registering the same token detaches it from any prior owner."""
    user1 = await _seed_user(test_db, "patient")
    user2 = await _seed_user(test_db, "doctor")
    token_str = "shared_device_tok_1"

    # First user registers
    r1 = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": token_str, "platform": "ios"},
        headers=auth("patient", sub=str(user1)),
    )
    assert r1.status_code == 201

    # Second user registers same token
    r2 = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": token_str, "platform": "ios"},
        headers=auth("doctor", sub=str(user2)),
    )
    assert r2.status_code == 201


# ── DELETE /notifications/token/{token} ─────────────────────────────────────


async def test_unregister_token_no_auth(client):
    """No bearer → 403."""
    resp = await client.delete("/api/v1/notifications/token/some_token")
    assert resp.status_code == 403


async def test_unregister_token_happy(client, test_db):
    """Unregister an existing token → 204."""
    user_uuid = await _seed_user(test_db)
    token_str = "delete_me_token_1234"

    # Register first
    await client.post(
        "/api/v1/notifications/register-token",
        json={"token": token_str, "platform": "android"},
        headers=auth("patient", sub=str(user_uuid)),
    )

    # Unregister
    resp = await client.delete(
        f"/api/v1/notifications/token/{token_str}",
        headers=auth("patient", sub=str(user_uuid)),
    )
    assert resp.status_code == 204


async def test_unregister_token_not_found(client, test_db):
    """Unregister a non-existent token → 404."""
    user_uuid = await _seed_user(test_db)
    resp = await client.delete(
        "/api/v1/notifications/token/nonexistent_token",
        headers=auth("patient", sub=str(user_uuid)),
    )
    assert resp.status_code == 404


# ── GET /notifications/inbox ────────────────────────────────────────────────


async def test_inbox_no_auth(client):
    """No bearer → 403."""
    resp = await client.get("/api/v1/notifications/inbox")
    assert resp.status_code == 403


async def test_inbox_empty(client, test_db):
    """Patient with no sent reminders → empty list."""
    user_uuid = await _seed_user(test_db)
    resp = await client.get(
        "/api/v1/notifications/inbox",
        headers=auth("patient", sub=str(user_uuid)),
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_inbox_returns_sent_reminders(client, test_db):
    """Patient sees their sent SMS reminders in inbox."""
    patient_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()

    # Seed user, patient, doctor, appointment, sms log
    user = User(
        user_uuid=patient_uuid,
        email=f"p-{patient_uuid}@test.ai",
        hashed_password="hashed",
        role=UserRole.PATIENT,
        first_name="P",
        last_name="T",
        is_active=True,
    )
    patient = Patient(
        patient_uuid=patient_uuid,
        consent_iot=False, consent_nlp=False, consent_sharing=False,
        sms_opt_out=False, birth_year=1990, sex="M",
        city_code="20000", chronic_conditions=[],
    )
    doc = User(
        user_uuid=doctor_uuid,
        email=f"d-{doctor_uuid}@test.ai",
        hashed_password="hashed",
        role=UserRole.DOCTOR,
        first_name="D", last_name="T", is_active=True,
    )
    appt_uuid = uuid.uuid4()
    appt = Appointment(
        appointment_uuid=appt_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
    )
    now = datetime.now(timezone.utc)
    log = SmsReminderLog(
        appointment_uuid=appt_uuid,
        task_type="sms_reminder",
        status="sent",
        scheduled_for=now,
        scheduled_date=now.date(),
    )
    test_db.add_all([user, patient, doc])
    await test_db.flush()
    test_db.add(appt)
    await test_db.flush()
    test_db.add(log)
    await test_db.flush()

    resp = await client.get(
        "/api/v1/notifications/inbox",
        headers=auth("patient", sub=str(patient_uuid)),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["appointment_uuid"] == str(appt_uuid)
    assert items[0]["title"] == "Rappel de rendez-vous"
