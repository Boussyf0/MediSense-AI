"""
Tests for POST /admin/patients — atomic patient creation with ML demographics.

Verifies:
  - Happy path: User + Patient rows created with shared UUID
  - Duplicate email → 409
  - Non-admin caller → 403
  - Missing required fields → 422
  - Invalid birth_year / sex pattern → 422
"""
import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.db.models.patient import Patient
from app.db.models.user import User


def admin_token() -> str:
    return create_access_token(subject=str(uuid.uuid4()), role="admin")


def doctor_token() -> str:
    return create_access_token(subject=str(uuid.uuid4()), role="doctor")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def patient_payload(**overrides) -> dict:
    base = {
        "email": f"patient_{uuid.uuid4().hex[:8]}@test.ma",
        "password": "SecurePass123",
        "first_name": "Fatima",
        "last_name": "Alaoui",
        "birth_year": 1988,
        "sex": "F",
        "city_code": "40000",
        "chronic_conditions": ["hypertension"],
    }
    return {**base, **overrides}


@pytest.mark.asyncio
async def test_create_patient_returns_201(client, test_db):
    payload = patient_payload()
    response = await client.post(
        "/api/v1/admin/patients",
        json=payload,
        headers=auth(admin_token()),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["birth_year"] == 1988
    assert data["sex"] == "F"
    assert data["city_code"] == "40000"
    assert data["chronic_conditions"] == ["hypertension"]
    assert data["is_active"] is True
    assert "patient_uuid" in data


@pytest.mark.asyncio
async def test_create_patient_user_and_patient_share_uuid(client, test_db):
    """User.user_uuid must equal Patient.patient_uuid so booking works."""
    payload = patient_payload()
    response = await client.post(
        "/api/v1/admin/patients",
        json=payload,
        headers=auth(admin_token()),
    )
    assert response.status_code == 201
    patient_uuid = uuid.UUID(response.json()["patient_uuid"])

    user_row = (
        await test_db.execute(select(User).where(User.user_uuid == patient_uuid))
    ).scalar_one_or_none()
    patient_row = (
        await test_db.execute(select(Patient).where(Patient.patient_uuid == patient_uuid))
    ).scalar_one_or_none()

    assert user_row is not None, "User row must exist"
    assert patient_row is not None, "Patient row must exist"
    assert user_row.role.value == "patient"
    assert patient_row.birth_year == payload["birth_year"]


@pytest.mark.asyncio
async def test_create_patient_no_demographics(client, test_db):
    """All demographic fields are optional."""
    payload = {
        "email": f"minimal_{uuid.uuid4().hex[:8]}@test.ma",
        "password": "SecurePass123",
    }
    response = await client.post(
        "/api/v1/admin/patients",
        json=payload,
        headers=auth(admin_token()),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["birth_year"] is None
    assert data["sex"] is None


@pytest.mark.asyncio
async def test_create_patient_duplicate_email_409(client, test_db):
    payload = patient_payload()
    r1 = await client.post("/api/v1/admin/patients", json=payload, headers=auth(admin_token()))
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/admin/patients", json=payload, headers=auth(admin_token()))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_patient_non_admin_403(client):
    response = await client.post(
        "/api/v1/admin/patients",
        json=patient_payload(),
        headers=auth(doctor_token()),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_patient_no_auth_403(client):
    response = await client.post("/api/v1/admin/patients", json=patient_payload())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_patient_invalid_birth_year_422(client):
    response = await client.post(
        "/api/v1/admin/patients",
        json=patient_payload(birth_year=1850),
        headers=auth(admin_token()),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_patient_invalid_sex_422(client):
    response = await client.post(
        "/api/v1/admin/patients",
        json=patient_payload(sex="X"),
        headers=auth(admin_token()),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_patient_short_password_422(client):
    response = await client.post(
        "/api/v1/admin/patients",
        json=patient_payload(password="short"),
        headers=auth(admin_token()),
    )
    assert response.status_code == 422
