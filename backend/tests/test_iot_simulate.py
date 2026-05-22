"""
Tests for POST /iot/simulate — demo device + biometric seed data.

Verifies:
  - Happy path: device paired, 168 readings inserted
  - Non-patient caller → 403
  - Patient without Patient record → 404
  - Idempotent: second call upserts device and replaces readings
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.biometric_reading import BiometricReading
from app.db.models.iot_device import IotDevice
from app.db.models.patient import Patient


def patient_token(patient_uuid: uuid.UUID) -> str:
    return create_access_token(subject=str(patient_uuid), role="patient")


def doctor_token() -> str:
    return create_access_token(subject=str(uuid.uuid4()), role="doctor")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def seed_patient(test_db, patient_uuid: uuid.UUID | None = None) -> uuid.UUID:
    patient_uuid = patient_uuid or uuid.uuid4()
    test_db.add(Patient(
        patient_uuid=patient_uuid,
        consent_iot=True,
        birth_year=1990,
        sex="M",
    ))
    await test_db.flush()
    return patient_uuid


@pytest.mark.asyncio
async def test_simulate_returns_200_with_device_paired(client, test_db):
    patient_uuid = await seed_patient(test_db)
    response = await client.post(
        "/api/v1/iot/simulate",
        headers=auth(patient_token(patient_uuid)),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["paired"] is True
    assert data["battery"] == 85
    assert data["last_sync"] is not None


@pytest.mark.asyncio
async def test_simulate_inserts_168_readings(client, test_db):
    patient_uuid = await seed_patient(test_db)
    response = await client.post(
        "/api/v1/iot/simulate",
        headers=auth(patient_token(patient_uuid)),
    )
    assert response.status_code == 200

    rows = (
        await test_db.execute(
            select(BiometricReading).where(BiometricReading.patient_uuid == patient_uuid)
        )
    ).scalars().all()
    assert len(rows) == 168
    # Spot-check value ranges
    for r in rows:
        assert 50 <= r.hr <= 110
        assert 95 <= r.spo2 <= 100
        assert 20 <= r.hrv <= 70


@pytest.mark.asyncio
async def test_simulate_creates_iot_device_record(client, test_db):
    patient_uuid = await seed_patient(test_db)
    await client.post(
        "/api/v1/iot/simulate",
        headers=auth(patient_token(patient_uuid)),
    )
    device = (
        await test_db.execute(
            select(IotDevice).where(IotDevice.patient_uuid == patient_uuid)
        )
    ).scalar_one_or_none()
    assert device is not None
    assert device.paired is True
    assert device.battery == 85


@pytest.mark.asyncio
async def test_simulate_idempotent(client, test_db):
    """Calling simulate twice must not raise and must reset to 168 readings."""
    patient_uuid = await seed_patient(test_db)
    headers = auth(patient_token(patient_uuid))

    r1 = await client.post("/api/v1/iot/simulate", headers=headers)
    assert r1.status_code == 200

    r2 = await client.post("/api/v1/iot/simulate", headers=headers)
    assert r2.status_code == 200

    rows = (
        await test_db.execute(
            select(BiometricReading).where(BiometricReading.patient_uuid == patient_uuid)
        )
    ).scalars().all()
    assert len(rows) == 168


@pytest.mark.asyncio
async def test_simulate_non_patient_403(client):
    response = await client.post(
        "/api/v1/iot/simulate",
        headers=auth(doctor_token()),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_simulate_no_auth_403(client):
    response = await client.post("/api/v1/iot/simulate")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_simulate_patient_without_record_404(client, test_db):
    """JWT is valid patient role but no Patient row exists → 404."""
    ghost_uuid = uuid.uuid4()
    response = await client.post(
        "/api/v1/iot/simulate",
        headers=auth(patient_token(ghost_uuid)),
    )
    assert response.status_code == 404
