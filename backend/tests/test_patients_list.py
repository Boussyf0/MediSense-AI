"""
Tests for the GET /patients list endpoint — the clinical roster used by the
web `/patients` page.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient


def auth_for(role: str) -> dict[str, str]:
    token = create_access_token(subject=str(uuid.uuid4()), role=role)
    return {"Authorization": f"Bearer {token}"}


async def _seed_patient(test_db, *, is_active: bool = True, **kwargs) -> Patient:
    patient = Patient(
        consent_iot=False,
        consent_nlp=False,
        consent_sharing=False,
        sms_opt_out=False,
        birth_year=kwargs.get("birth_year", 1985),
        sex=kwargs.get("sex", "M"),
        city_code=kwargs.get("city_code", "40000"),
        chronic_conditions=kwargs.get("chronic_conditions", []),
        is_active=is_active,
    )
    test_db.add(patient)
    await test_db.flush()
    return patient


@pytest.mark.asyncio
async def test_list_patients_happy_path(client, test_db):
    """Doctor lists active patients with last/next appointment timestamps."""
    p1 = await _seed_patient(test_db, birth_year=1990, sex="F", city_code="20000")
    p2 = await _seed_patient(test_db, birth_year=1980, sex="M", city_code="40000")

    doctor_uuid = uuid.uuid4()
    from app.db.models.user import User, UserRole
    test_db.add(
        User(
            user_uuid=doctor_uuid,
            email=f"dr-{doctor_uuid}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Test",
            last_name="Doctor",
            is_active=True,
        )
    )
    await test_db.flush()

    now = datetime.now(timezone.utc)
    test_db.add(
        Appointment(
            appointment_uuid=uuid.uuid4(),
            patient_uuid=p1.patient_uuid,
            doctor_uuid=doctor_uuid,
            scheduled_at=now - timedelta(days=3),
            duration_minutes=20,
            status="COMPLETED",
        )
    )
    test_db.add(
        Appointment(
            appointment_uuid=uuid.uuid4(),
            patient_uuid=p1.patient_uuid,
            doctor_uuid=doctor_uuid,
            scheduled_at=now + timedelta(days=5),
            duration_minutes=20,
            status="PENDING",
        )
    )
    await test_db.flush()

    response = await client.get(
        "/api/v1/patients?limit=10&offset=0",
        headers=auth_for("doctor"),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert data["total"] >= 2

    by_uuid = {item["patient_uuid"]: item for item in data["items"]}
    assert str(p1.patient_uuid) in by_uuid
    assert str(p2.patient_uuid) in by_uuid

    p1_row = by_uuid[str(p1.patient_uuid)]
    assert p1_row["birth_year"] == 1990
    assert p1_row["sex"] == "F"
    assert p1_row["is_active"] is True
    assert p1_row["last_appointment_at"] is not None
    assert p1_row["next_appointment_at"] is not None

    p2_row = by_uuid[str(p2.patient_uuid)]
    assert p2_row["last_appointment_at"] is None
    assert p2_row["next_appointment_at"] is None


@pytest.mark.asyncio
async def test_list_patients_only_active_filters_erased(client, test_db):
    """When only_active=True (default), inactive (erased) patients are excluded."""
    active = await _seed_patient(test_db, is_active=True)
    erased = await _seed_patient(test_db, is_active=False)

    response = await client.get(
        "/api/v1/patients",
        headers=auth_for("doctor"),
    )

    assert response.status_code == 200
    uuids = {item["patient_uuid"] for item in response.json()["items"]}
    assert str(active.patient_uuid) in uuids
    assert str(erased.patient_uuid) not in uuids


@pytest.mark.asyncio
async def test_list_patients_requires_auth(client):
    """HTTPBearer returns 403 when Authorization header is absent."""
    response = await client.get("/api/v1/patients")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_patients_patient_role_forbidden(client):
    """Patients must not be able to enumerate the clinical roster."""
    response = await client.get(
        "/api/v1/patients",
        headers=auth_for("patient"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_patients_invalid_pagination_returns_422(client):
    """limit=0 violates the ge=1 constraint and must return 422."""
    response = await client.get(
        "/api/v1/patients?limit=0",
        headers=auth_for("doctor"),
    )
    assert response.status_code == 422


# ── PATCH /patients/me/consent ────────────────────────────

def _patient_auth(patient_uuid: uuid.UUID) -> dict[str, str]:
    token = create_access_token(subject=str(patient_uuid), role="patient")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_update_own_consent_happy_path(client, test_db):
    """Patient updates their own consent flags; response reflects new state."""
    patient = await _seed_patient(test_db, birth_year=1995, sex="F")
    headers = _patient_auth(patient.patient_uuid)

    response = await client.patch(
        "/api/v1/patients/me/consent",
        json={"consent_iot": True, "consent_nlp": True, "channel": "app"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["consent_iot"] is True
    assert data["consent_nlp"] is True


@pytest.mark.asyncio
async def test_update_own_consent_idempotent(client, test_db):
    """Sending the same value twice returns 200 without changing the state."""
    patient = await _seed_patient(test_db, birth_year=1990)
    patient.consent_iot = True
    await test_db.flush()

    headers = _patient_auth(patient.patient_uuid)
    response = await client.patch(
        "/api/v1/patients/me/consent",
        json={"consent_iot": True, "channel": "app"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["consent_iot"] is True


@pytest.mark.asyncio
async def test_update_own_consent_requires_auth(client):
    """HTTPBearer returns 403 when Authorization header is absent."""
    response = await client.patch(
        "/api/v1/patients/me/consent",
        json={"consent_iot": True, "channel": "app"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_own_consent_doctor_role_forbidden(client):
    """Doctor role must not use the patient self-service consent endpoint."""
    response = await client.patch(
        "/api/v1/patients/me/consent",
        json={"consent_iot": True, "channel": "app"},
        headers=auth_for("doctor"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_own_consent_patient_not_found(client):
    """Returns 404 when the JWT sub does not match any Patient row."""
    unknown_uuid = uuid.uuid4()
    headers = _patient_auth(unknown_uuid)

    response = await client.patch(
        "/api/v1/patients/me/consent",
        json={"consent_iot": True, "channel": "app"},
        headers=headers,
    )
    assert response.status_code == 404
