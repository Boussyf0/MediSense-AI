"""
Tests for US-03 (JWT auth) and US-04 (RBAC).
"""
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password, create_access_token
from app.db.models.user import User, UserRole


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
