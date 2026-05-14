import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from app.db.models.biometric_reading import BiometricReading
from app.db.models.iot_device import IotDevice
from app.db.models.patient import Patient


def auth_for(patient_uuid: uuid.UUID) -> dict[str, str]:
    token = create_access_token(subject=str(patient_uuid), role="patient")
    return {"Authorization": f"Bearer {token}"}


async def seed_patient(test_db, patient_uuid: uuid.UUID | None = None) -> uuid.UUID:
    patient_uuid = patient_uuid or uuid.uuid4()
    test_db.add(Patient(
        patient_uuid=patient_uuid,
        consent_iot=True,
        consent_nlp=False,
        consent_sharing=False,
        sms_opt_out=False,
        birth_year=1990,
        sex="M",
        city_code="40000",
        chronic_conditions=[],
    ))
    await test_db.flush()
    return patient_uuid


@pytest.mark.asyncio
async def test_vitals_returns_seeded_points(client, test_db):
    patient_uuid = await seed_patient(test_db)
    now = datetime.now(timezone.utc)
    for i in range(4):
        test_db.add(BiometricReading(
            patient_uuid=patient_uuid,
            ts=now - timedelta(days=i),
            hr=70 + i,
            spo2=97,
            hrv=45,
        ))
    await test_db.flush()

    response = await client.get(
        "/api/v1/iot/vitals?range=7d",
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    assert all("hr" in p and "spo2" in p and "hrv" in p and "ts" in p for p in data)


@pytest.mark.asyncio
async def test_vitals_filters_out_of_range(client, test_db):
    patient_uuid = await seed_patient(test_db)
    now = datetime.now(timezone.utc)
    test_db.add(BiometricReading(
        patient_uuid=patient_uuid,
        ts=now - timedelta(days=30),
        hr=70, spo2=97, hrv=45,
    ))
    test_db.add(BiometricReading(
        patient_uuid=patient_uuid,
        ts=now - timedelta(hours=1),
        hr=72, spo2=98, hrv=46,
    ))
    await test_db.flush()

    response = await client.get(
        "/api/v1/iot/vitals?range=24h",
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_vitals_no_auth_403(client):
    response = await client.get("/api/v1/iot/vitals?range=7d")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_vitals_invalid_range_422(client, test_db):
    patient_uuid = await seed_patient(test_db)
    response = await client.get(
        "/api/v1/iot/vitals?range=foobar",
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_devices_returns_paired(client, test_db):
    patient_uuid = await seed_patient(test_db)
    test_db.add(IotDevice(
        patient_uuid=patient_uuid,
        paired=True,
        last_sync=datetime.now(timezone.utc),
        battery=87,
    ))
    await test_db.flush()

    response = await client.get(
        "/api/v1/iot/devices",
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["paired"] is True
    assert data["battery"] == 87


@pytest.mark.asyncio
async def test_devices_404_when_missing(client, test_db):
    patient_uuid = await seed_patient(test_db)
    response = await client.get(
        "/api/v1/iot/devices",
        headers=auth_for(patient_uuid),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_devices_no_auth_403(client):
    response = await client.get("/api/v1/iot/devices")
    assert response.status_code == 403
