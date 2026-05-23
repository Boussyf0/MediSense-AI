"""Tests for the GET /doctors directory endpoint."""
import uuid

import pytest

from app.core.security import create_access_token
from app.db.models.user import User, UserRole


def auth_for(role: str) -> dict[str, str]:
    token = create_access_token(subject=str(uuid.uuid4()), role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_list_doctors_returns_active_doctors(client, test_db):
    active = uuid.uuid4()
    inactive = uuid.uuid4()
    secretary = uuid.uuid4()

    test_db.add_all([
        User(
            user_uuid=active,
            email=f"dr-{active}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Amine",
            last_name="Bennani",
            is_active=True,
        ),
        User(
            user_uuid=inactive,
            email=f"dr-{inactive}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Old",
            last_name="Doctor",
            is_active=False,
        ),
        User(
            user_uuid=secretary,
            email=f"sec-{secretary}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.SECRETARY,
            first_name="Sara",
            last_name="Alami",
            is_active=True,
        ),
    ])
    await test_db.flush()

    response = await client.get("/api/v1/doctors", headers=auth_for("patient"))

    assert response.status_code == 200
    uuids = {item["user_uuid"] for item in response.json()}
    assert str(active) in uuids
    assert str(inactive) not in uuids
    assert str(secretary) not in uuids

    active_row = next(i for i in response.json() if i["user_uuid"] == str(active))
    assert active_row["display_name"] == "Dr. Amine Bennani"


@pytest.mark.asyncio
async def test_list_doctors_requires_auth(client):
    response = await client.get("/api/v1/doctors")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_doctors_returns_specialty(client, test_db):
    """Directory must expose specialty so the mobile UI can show it."""
    cardio = uuid.uuid4()
    test_db.add(
        User(
            user_uuid=cardio,
            email=f"dr-{cardio}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Sara",
            last_name="Tahiri",
            specialty="Cardiologie",
            is_active=True,
        )
    )
    await test_db.flush()

    response = await client.get("/api/v1/doctors", headers=auth_for("patient"))
    assert response.status_code == 200
    row = next(i for i in response.json() if i["user_uuid"] == str(cardio))
    assert row["specialty"] == "Cardiologie"


@pytest.mark.asyncio
async def test_list_doctors_filters_by_specialty_query(client, test_db):
    cardio = uuid.uuid4()
    derma = uuid.uuid4()
    test_db.add_all([
        User(
            user_uuid=cardio,
            email=f"dr-{cardio}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Sara", last_name="Tahiri",
            specialty="Cardiologie", is_active=True,
        ),
        User(
            user_uuid=derma,
            email=f"dr-{derma}@medisense.ai",
            hashed_password="hashed",
            role=UserRole.DOCTOR,
            first_name="Imane", last_name="Berrada",
            specialty="Dermatologie", is_active=True,
        ),
    ])
    await test_db.flush()

    response = await client.get(
        "/api/v1/doctors?specialty=Cardiologie",
        headers=auth_for("patient"),
    )
    assert response.status_code == 200
    uuids = {i["user_uuid"] for i in response.json()}
    assert str(cardio) in uuids
    assert str(derma) not in uuids
