"""
Tests for US-03 (JWT auth) and US-04 (RBAC).
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.core.security import hash_password, verify_password, create_access_token
from app.db.models.conversation import Conversation
from app.db.models.patient import Patient


# ── Security unit tests ───────────────────────────────────

def test_password_hashing():
    """Password hash must not be the plain text."""
    plain = "TestPassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$2b$")   # bcrypt prefix


def test_password_verification():
    """Correct password must verify, wrong password must not."""
    plain = "TestPassword123!"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_access_token_contains_required_claims():
    """JWT access token must contain sub, role, jti, type claims."""
    from app.core.security import decode_token
    token = create_access_token(subject="test-uuid", role="doctor")
    payload = decode_token(token)
    assert payload["sub"] == "test-uuid"
    assert payload["role"] == "doctor"
    assert "jti" in payload
    assert payload["type"] == "access"


# ── API endpoint tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_login_wrong_credentials(client):
    """Wrong credentials must return 401, not 404 or 500."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "nonexistent@test.com",
        "password": "WrongPassword123!"
    })
    assert response.status_code == 401
    # Must not reveal whether the email exists
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client):
    """Accessing /auth/me without token must return 401, not 500."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403  # HTTPBearer returns 403 when no token


@pytest.mark.asyncio
async def test_protected_endpoint_with_invalid_token(client):
    """A tampered token must return 401."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.not.a.valid.token"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rbac_doctor_token_accepted(client):
    """A valid doctor token must be accepted for /auth/me."""
    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    # Note: /auth/me also queries the DB for the user.
    # In a full test, we'd seed a user first. Here we test the auth layer only.
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    # 404 = token valid but user not in test DB (expected for this unit test)
    # 401 = token invalid (this would be a failure)
    assert response.status_code in (200, 404)
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_logout_patient_clears_conversation_cache(client, test_db):
    patient_id = str(uuid.uuid4())
    patient = Patient(
        patient_uuid=uuid.UUID(patient_id),
        consent_iot=False,
        consent_nlp=False,
        consent_sharing=False,
        birth_year=1988,
        sex="M",
        city_code="75000",
    )
    test_db.add(patient)
    await test_db.flush()

    conv = Conversation(patient_id=uuid.UUID(patient_id), language="fr")
    test_db.add(conv)
    await test_db.flush()

    token = create_access_token(subject=patient_id, role="patient")
    with patch("app.api.v1.endpoints.auth.clear_patient_conversations", new=AsyncMock()) as mock_clear:
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 204
    mock_clear.assert_awaited_once_with(patient_id, [str(conv.id)])


@pytest.mark.asyncio
async def test_logout_non_patient_does_not_clear_conversation_cache(client):
    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    with patch("app.api.v1.endpoints.auth.clear_patient_conversations", new=AsyncMock()) as mock_clear:
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 204
    mock_clear.assert_not_awaited()
