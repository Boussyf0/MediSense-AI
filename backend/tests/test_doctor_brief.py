"""Tests for GET /api/v1/doctor/agenda/{appointment_uuid}/brief — Phase B."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.biometric_reading import BiometricReading
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole


def _auth(subject: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token(subject=str(subject), role=role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_appointment(
    test_db,
    *,
    with_vitals: bool = False,
    chronic: list[str] | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create patient + doctor + appointment. Returns (patient_uuid, doctor_uuid, appt_uuid)."""
    patient_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    appt_uuid = uuid.uuid4()

    test_db.add(
        Patient(
            patient_uuid=patient_uuid,
            consent_iot=False,
            consent_nlp=False,
            consent_sharing=False,
            sms_opt_out=False,
            birth_year=1985,
            sex="F",
            city_code="40000",
            chronic_conditions=chronic or [],
        )
    )
    test_db.add(
        User(
            user_uuid=patient_uuid,
            email=f"p-{patient_uuid}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.PATIENT,
            first_name="Asma",
            last_name="Patient",
            is_active=True,
        )
    )
    test_db.add(
        User(
            user_uuid=doctor_uuid,
            email=f"dr-{doctor_uuid}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Karim",
            last_name="Bennis",
            is_active=True,
        )
    )
    await test_db.flush()  # Patient must exist before Appointment FK.
    test_db.add(
        Appointment(
            appointment_uuid=appt_uuid,
            patient_uuid=patient_uuid,
            doctor_uuid=doctor_uuid,
            scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
            duration_minutes=20,
            status="PENDING",
        )
    )
    if with_vitals:
        now = datetime.now(timezone.utc)
        for i in range(3):
            test_db.add(
                BiometricReading(
                    id=uuid.uuid4(),
                    patient_uuid=patient_uuid,
                    ts=now - timedelta(minutes=10 * i),
                    hr=72 + i,
                    spo2=98,
                    hrv=42,
                )
            )
    await test_db.flush()
    return patient_uuid, doctor_uuid, appt_uuid


@pytest.mark.asyncio
async def test_brief_requires_auth(client):
    """HTTPBearer returns 403 when Authorization header absent."""
    resp = await client.get(f"/api/v1/doctor/agenda/{uuid.uuid4()}/brief")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_brief_rejects_patient_role(client, test_db):
    _, _, appt_uuid = await _seed_appointment(test_db)
    resp = await client.get(
        f"/api/v1/doctor/agenda/{appt_uuid}/brief",
        headers=_auth(uuid.uuid4(), "patient"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_brief_404_unknown_appointment(client):
    resp = await client.get(
        f"/api/v1/doctor/agenda/{uuid.uuid4()}/brief",
        headers=_auth(uuid.uuid4(), "doctor"),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_brief_happy_path_with_vitals(client, test_db):
    patient_uuid, doctor_uuid, appt_uuid = await _seed_appointment(
        test_db, with_vitals=True, chronic=["asthma"]
    )
    resp = await client.get(
        f"/api/v1/doctor/agenda/{appt_uuid}/brief",
        headers=_auth(doctor_uuid, "doctor"),
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["appointment_uuid"] == str(appt_uuid)
    assert body["patient"]["patient_uuid"] == str(patient_uuid)
    assert body["patient"]["display_name"] == "Asma Patient"
    assert body["patient"]["chronic_conditions"] == ["asthma"]
    assert body["patient"]["sex"] == "F"
    assert body["patient"]["age"] is not None

    assert body["vitals"]["samples_24h"] == 3
    assert body["vitals"]["hr"] in (72, 73, 74)
    assert body["vitals"]["spo2"] == 98

    # Anomaly degrades to empty fields without Redis seeding — endpoint still 200.
    assert "score_5m" in body["anomaly"]

    # No symptom messages seeded → empty list.
    assert body["recent_symptoms"] == []

    # No-show: model may or may not load in CI; either way we get a stable shape.
    assert "probability" in body["noshow"]


@pytest.mark.asyncio
async def test_brief_empty_data_returns_200(client, test_db):
    """Patient with no vitals, no chat, no model artefacts still yields a valid brief."""
    _, doctor_uuid, appt_uuid = await _seed_appointment(test_db)
    resp = await client.get(
        f"/api/v1/doctor/agenda/{appt_uuid}/brief",
        headers=_auth(doctor_uuid, "doctor"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["vitals"]["samples_24h"] == 0
    assert body["vitals"]["hr"] is None
    assert body["recent_symptoms"] == []
