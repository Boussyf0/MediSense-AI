import uuid
from datetime import datetime, timezone

import pytest

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole


def auth_for(subject: uuid.UUID, role: str) -> dict[str, str]:
    token = create_access_token(subject=str(subject), role=role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_patient(test_db, patient_uuid: uuid.UUID, *, doctor_uuid: uuid.UUID) -> None:
    test_db.add(
        Patient(
            patient_uuid=patient_uuid,
            consent_iot=False,
            consent_nlp=False,
            consent_sharing=False,
            sms_opt_out=False,
            birth_year=1990,
            sex="M",
            city_code="40000",
            chronic_conditions=[],
        )
    )
    test_db.add(
        User(
            user_uuid=doctor_uuid,
            email=f"dr-{doctor_uuid}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Amine",
            last_name="Bennani",
            is_active=True,
        )
    )
    await test_db.flush()


@pytest.mark.asyncio
async def test_appointments_patient_sees_own_appointments(client, test_db):
    patient_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    await _seed_patient(test_db, patient_uuid, doctor_uuid=doctor_uuid)

    test_db.add(
        Appointment(
            appointment_uuid=uuid.uuid4(),
            patient_uuid=patient_uuid,
            doctor_uuid=doctor_uuid,
            scheduled_at=datetime(2026, 6, 1, 10, 30, tzinfo=timezone.utc),
            duration_minutes=20,
            status="PENDING",
            noshow_probability=0.45,
        )
    )
    await test_db.flush()

    response = await client.get(
        "/api/v1/appointments?date=2026-06-01",
        headers=auth_for(patient_uuid, "patient"),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["risk_color"] == "red"
    assert data[0]["appointment_time"] == "10:30"
    assert data[0]["doctor_name"] == "Dr. Amine Bennani"


@pytest.mark.asyncio
async def test_appointments_patient_does_not_see_others(client, test_db):
    me_uuid = uuid.uuid4()
    other_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    await _seed_patient(test_db, me_uuid, doctor_uuid=doctor_uuid)
    test_db.add(
        Patient(
            patient_uuid=other_uuid,
            consent_iot=False,
            consent_nlp=False,
            consent_sharing=False,
            sms_opt_out=False,
            birth_year=1985,
            sex="F",
            city_code="40000",
            chronic_conditions=[],
        )
    )
    await test_db.flush()
    test_db.add(
        Appointment(
            appointment_uuid=uuid.uuid4(),
            patient_uuid=other_uuid,
            doctor_uuid=doctor_uuid,
            scheduled_at=datetime(2026, 6, 1, 11, 0, tzinfo=timezone.utc),
            duration_minutes=20,
            status="PENDING",
            noshow_probability=0.10,
        )
    )
    await test_db.flush()

    response = await client.get(
        "/api/v1/appointments?date=2026-06-01",
        headers=auth_for(me_uuid, "patient"),
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_appointments_requires_auth(client):
    response = await client.get("/api/v1/appointments")
    # HTTPBearer returns 403 when Authorization header is absent
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_appointments_invalid_date_returns_422(client):
    patient_uuid = uuid.uuid4()
    response = await client.get(
        "/api/v1/appointments?date=not-a-date",
        headers=auth_for(patient_uuid, "patient"),
    )
    assert response.status_code == 422


# ── POST /appointments — booking ────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_appointment_patient_books_for_self(client, test_db):
    patient_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    await _seed_patient(test_db, patient_uuid, doctor_uuid=doctor_uuid)

    from datetime import timedelta
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)

    response = await client.post(
        "/api/v1/appointments",
        json={
            "patient_uuid": str(patient_uuid),
            "doctor_uuid": str(doctor_uuid),
            "scheduled_at": scheduled_at.isoformat(),
            "duration_minutes": 30,
        },
        headers=auth_for(patient_uuid, "patient"),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["patient_uuid"] == str(patient_uuid)
    assert data["doctor_uuid"] == str(doctor_uuid)
    assert data["duration_minutes"] == 30
    assert data["status"] == "PENDING"
    assert data["doctor_name"] == "Dr. Amine Bennani"


@pytest.mark.asyncio
async def test_create_appointment_patient_cannot_book_for_other(client, test_db):
    me_uuid = uuid.uuid4()
    other_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    await _seed_patient(test_db, me_uuid, doctor_uuid=doctor_uuid)
    test_db.add(
        Patient(
            patient_uuid=other_uuid,
            consent_iot=False, consent_nlp=False, consent_sharing=False,
            sms_opt_out=False, birth_year=1985, sex="F",
            city_code="40000", chronic_conditions=[],
        )
    )
    await test_db.flush()

    from datetime import timedelta
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)

    response = await client.post(
        "/api/v1/appointments",
        json={
            "patient_uuid": str(other_uuid),
            "doctor_uuid": str(doctor_uuid),
            "scheduled_at": scheduled_at.isoformat(),
        },
        headers=auth_for(me_uuid, "patient"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_appointment_requires_auth(client):
    response = await client.post(
        "/api/v1/appointments",
        json={
            "patient_uuid": str(uuid.uuid4()),
            "doctor_uuid": str(uuid.uuid4()),
            "scheduled_at": "2030-01-01T10:00:00+00:00",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_appointment_past_datetime_returns_422(client, test_db):
    patient_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    await _seed_patient(test_db, patient_uuid, doctor_uuid=doctor_uuid)

    response = await client.post(
        "/api/v1/appointments",
        json={
            "patient_uuid": str(patient_uuid),
            "doctor_uuid": str(doctor_uuid),
            "scheduled_at": "2000-01-01T10:00:00+00:00",
        },
        headers=auth_for(patient_uuid, "patient"),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_appointment_unknown_doctor_returns_404(client, test_db):
    patient_uuid = uuid.uuid4()
    real_doctor_uuid = uuid.uuid4()
    await _seed_patient(test_db, patient_uuid, doctor_uuid=real_doctor_uuid)

    from datetime import timedelta
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)

    response = await client.post(
        "/api/v1/appointments",
        json={
            "patient_uuid": str(patient_uuid),
            "doctor_uuid": str(uuid.uuid4()),  # nobody
            "scheduled_at": scheduled_at.isoformat(),
        },
        headers=auth_for(patient_uuid, "patient"),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_appointment_conflict_returns_409(client, test_db):
    patient_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    await _seed_patient(test_db, patient_uuid, doctor_uuid=doctor_uuid)

    from datetime import timedelta
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=4)).replace(microsecond=0)

    test_db.add(
        Appointment(
            appointment_uuid=uuid.uuid4(),
            patient_uuid=patient_uuid,
            doctor_uuid=doctor_uuid,
            scheduled_at=scheduled_at,
            duration_minutes=20,
            status="PENDING",
        )
    )
    await test_db.flush()

    response = await client.post(
        "/api/v1/appointments",
        json={
            "patient_uuid": str(patient_uuid),
            "doctor_uuid": str(doctor_uuid),
            "scheduled_at": scheduled_at.isoformat(),
        },
        headers=auth_for(patient_uuid, "patient"),
    )
    assert response.status_code == 409
