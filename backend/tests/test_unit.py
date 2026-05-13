"""
Pure unit tests for synchronous utility functions and Pydantic schema validators.

These tests cover specific branches that require no DB or HTTP — they exist
solely to keep the coverage gate above 80% for code that's otherwise exercised
only through async endpoint tests (which have a known coverage-tracking gap for
lines that execute after the first await db.execute() call).
"""
import uuid
import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError


# ── app/core/security.py ──────────────────────────────────

def test_create_access_token_with_extra_claims():
    from app.core.security import create_access_token, decode_token
    token = create_access_token(str(uuid.uuid4()), "doctor", extra_claims={"dept": "cardio"})
    payload = decode_token(token)
    assert payload["dept"] == "cardio"


def test_check_permission_doctor_has_patients_access():
    from app.core.security import check_permission
    assert check_permission("doctor", "/api/v1/patients/some-uuid") is True


def test_check_permission_patient_has_no_admin_access():
    from app.core.security import check_permission
    assert check_permission("patient", "/api/v1/admin/users") is False


# ── app/core/audit.py ─────────────────────────────────────

def test_get_client_ip_returns_x_real_ip_header():
    from app.core.audit import _get_client_ip
    request = MagicMock()
    request.headers.get = lambda k: "10.0.0.1" if k == "X-Real-IP" else None
    assert _get_client_ip(request) == "10.0.0.1"


# ── app/schemas/reminders.py ──────────────────────────────

def test_reminder_create_invalid_day_raises():
    from app.schemas.reminders import ReminderCreate
    with pytest.raises(ValidationError):
        ReminderCreate(name="Test", dosage="500mg", time="08:00:00", days_of_week=[7])


def test_reminder_update_none_days_of_week():
    from app.schemas.reminders import ReminderUpdate
    model = ReminderUpdate(days_of_week=None)
    assert model.days_of_week is None


def test_reminder_update_valid_days_of_week():
    from app.schemas.reminders import ReminderUpdate
    model = ReminderUpdate(days_of_week=[1, 3, 5])
    assert model.days_of_week == [1, 3, 5]


# ── app/schemas/auth.py ───────────────────────────────────

def test_login_request_short_password_raises():
    from app.schemas.auth import LoginRequest
    with pytest.raises(ValidationError):
        LoginRequest(email="user@example.com", password="short")


# ── app/schemas/crm.py ────────────────────────────────────

def test_crm_task_patch_task_id_too_long_raises():
    from app.schemas.crm import CRMTaskPatch
    with pytest.raises(ValidationError):
        CRMTaskPatch(salesforce_task_id="x" * 101)


def test_crm_task_patch_valid_sync_status():
    from app.schemas.crm import CRMTaskPatch
    model = CRMTaskPatch(crm_sync_status="PENDING")
    assert model.crm_sync_status == "PENDING"


# ── app/schemas/patient.py ────────────────────────────────

def test_consent_update_cgu_version_too_long_raises():
    from app.schemas.patient import ConsentUpdate
    with pytest.raises(ValidationError):
        ConsentUpdate(cgu_version="v" * 21, channel="app")


# ── app/core/conversation_cache.py ───────────────────────

def test_redis_url_returns_valid_url():
    from app.core.conversation_cache import _redis_url
    url = _redis_url()
    assert url.startswith("redis://")


# ── app/rag/iot_context.py ───────────────────────────────

def test_build_summary_text_empty_list():
    from app.rag.iot_context import _build_summary_text
    assert _build_summary_text([]) == ""


@pytest.mark.asyncio
async def test_fetch_iot_context_with_none_db():
    from app.rag.iot_context import fetch_iot_context, IoTContext
    result = await fetch_iot_context(str(uuid.uuid4()), db=None)
    assert isinstance(result, IoTContext)
    assert result.is_empty


# ── app/rag/language.py ───────────────────────────────────

def test_arabic_char_ratio_empty_string():
    from app.rag.language import _arabic_char_ratio
    assert _arabic_char_ratio("") == 0.0


# ── app/core/dependencies.py (needs HTTP client) ─────────

@pytest.mark.asyncio
async def test_refresh_token_used_as_access_token_returns_401(client):
    from app.core.security import create_refresh_token
    refresh_tok, _ = create_refresh_token(subject=str(uuid.uuid4()), role="patient")
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_tok}"},
    )
    assert response.status_code == 401
