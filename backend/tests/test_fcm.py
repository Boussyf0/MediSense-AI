"""FCM service + notifications endpoints — Sprint 7 (US-29)."""
import uuid

import pytest

from app.core.security import create_access_token
from app.db.models.user import User, UserRole
from app.services import fcm_service


def _doctor_headers() -> dict[str, str]:
    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    return {"Authorization": f"Bearer {token}"}


async def _seed_doctor(test_db) -> tuple[uuid.UUID, dict[str, str]]:
    """Create a real users row so device_token's FK is satisfied."""
    user_uuid = uuid.uuid4()
    test_db.add(User(
        user_uuid=user_uuid,
        email=f"dr-{user_uuid}@medisense.ai",
        hashed_password="hashed",
        role=UserRole.DOCTOR,
        first_name="Test",
        last_name="Doctor",
        is_active=True,
    ))
    await test_db.flush()
    token = create_access_token(subject=str(user_uuid), role="doctor")
    return user_uuid, {"Authorization": f"Bearer {token}"}


# ── fcm_service ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_to_token_mock_mode_returns_true(monkeypatch):
    """Without a service-account, FCM logs and returns True."""
    fcm_service.reset_for_tests()
    monkeypatch.setattr(
        "app.services.fcm_service.get_settings",
        lambda: type("S", (), {"FCM_SERVICE_ACCOUNT_B64": ""})(),
    )
    ok = await fcm_service.send_to_token("dummy-token-12345", "T", "B", {"k": "v"})
    assert ok is True


@pytest.mark.asyncio
async def test_send_to_tokens_counts_successes(monkeypatch):
    fcm_service.reset_for_tests()
    monkeypatch.setattr(
        "app.services.fcm_service.get_settings",
        lambda: type("S", (), {"FCM_SERVICE_ACCOUNT_B64": ""})(),
    )
    sent = await fcm_service.send_to_tokens(["t1xxxxxxxxxx", "t2xxxxxxxxxx"], "T", "B")
    assert sent == 2


@pytest.mark.asyncio
async def test_send_to_tokens_empty_returns_zero():
    sent = await fcm_service.send_to_tokens([], "T", "B")
    assert sent == 0


# ── /notifications endpoints ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_token_requires_auth(client):
    """HTTPBearer returns 403 when Authorization header absent."""
    resp = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "x" * 20, "platform": "android"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_token_happy_path(client, test_db):
    _, headers = await _seed_doctor(test_db)
    resp = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "fcm-token-abcdef-1234567890", "platform": "android"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token"] == "fcm-token-abcdef-1234567890"
    assert body["platform"] == "android"
    assert "id" in body


@pytest.mark.asyncio
async def test_register_token_rebinds_existing(client, test_db):
    """Same token registered twice → second insert succeeds (prior row replaced)."""
    _, headers = await _seed_doctor(test_db)
    payload = {"token": "fcm-rebind-token-0001", "platform": "ios"}
    r1 = await client.post("/api/v1/notifications/register-token", json=payload, headers=headers)
    r2 = await client.post("/api/v1/notifications/register-token", json=payload, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_unregister_token_404_when_missing(client):
    resp = await client.delete(
        "/api/v1/notifications/token/never-registered-token",
        headers=_doctor_headers(),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unregister_token_204_when_owned(client, test_db):
    _, headers = await _seed_doctor(test_db)
    await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "fcm-to-delete-99999", "platform": "web"},
        headers=headers,
    )
    resp = await client.delete(
        "/api/v1/notifications/token/fcm-to-delete-99999",
        headers=headers,
    )
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_register_token_validation_rejects_short(client):
    resp = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "short", "platform": "android"},
        headers=_doctor_headers(),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_token_rejects_unknown_platform(client):
    resp = await client.post(
        "/api/v1/notifications/register-token",
        json={"token": "x" * 20, "platform": "windows"},
        headers=_doctor_headers(),
    )
    assert resp.status_code == 422
