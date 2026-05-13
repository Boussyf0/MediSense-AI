import uuid

import pytest

from app.core.security import create_access_token
from app.db.models.patient import Patient


def auth_for(patient_uuid: uuid.UUID) -> dict[str, str]:
    token = create_access_token(subject=str(patient_uuid), role="patient")
    return {"Authorization": f"Bearer {token}"}


async def seed_patient(test_db) -> uuid.UUID:
    patient_uuid = uuid.uuid4()
    test_db.add(Patient(
        patient_uuid=patient_uuid,
        consent_iot=False,
        consent_nlp=False,
        consent_sharing=False,
        sms_opt_out=False,
        birth_year=1990,
        sex="F",
        city_code="40000",
        chronic_conditions=[],
    ))
    await test_db.flush()
    return patient_uuid


_REM_PAYLOAD = {
    "name": "Paracetamol",
    "dosage": "500mg",
    "time": "08:00:00",
    "days_of_week": [0, 1, 2, 3, 4],
}


@pytest.mark.asyncio
async def test_create_reminder_201(client, test_db):
    patient_uuid = await seed_patient(test_db)
    response = await client.post(
        "/api/v1/reminders",
        json=_REM_PAYLOAD,
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Paracetamol"
    assert data["dosage"] == "500mg"
    assert data["enabled"] is True
    assert data["days_of_week"] == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_list_reminders_200(client, test_db):
    patient_uuid = await seed_patient(test_db)
    await client.post("/api/v1/reminders", json=_REM_PAYLOAD, headers=auth_for(patient_uuid))
    response = await client.get("/api/v1/reminders", headers=auth_for(patient_uuid))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_patch_reminder_200(client, test_db):
    patient_uuid = await seed_patient(test_db)
    create = await client.post(
        "/api/v1/reminders", json=_REM_PAYLOAD, headers=auth_for(patient_uuid)
    )
    rid = create.json()["id"]

    response = await client.patch(
        f"/api/v1/reminders/{rid}",
        json={"enabled": False, "dosage": "1g"},
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["dosage"] == "1g"


@pytest.mark.asyncio
async def test_delete_reminder_204(client, test_db):
    patient_uuid = await seed_patient(test_db)
    create = await client.post(
        "/api/v1/reminders", json=_REM_PAYLOAD, headers=auth_for(patient_uuid)
    )
    rid = create.json()["id"]

    response = await client.delete(
        f"/api/v1/reminders/{rid}", headers=auth_for(patient_uuid)
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_list_reminders_no_auth_403(client):
    response = await client.get("/api/v1/reminders")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patch_unknown_reminder_404(client, test_db):
    patient_uuid = await seed_patient(test_db)
    response = await client.patch(
        f"/api/v1/reminders/{uuid.uuid4()}",
        json={"enabled": False},
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_reminder_invalid_time_422(client, test_db):
    patient_uuid = await seed_patient(test_db)
    bad = {**_REM_PAYLOAD, "time": "25:99"}
    response = await client.post(
        "/api/v1/reminders",
        json=bad,
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 422
