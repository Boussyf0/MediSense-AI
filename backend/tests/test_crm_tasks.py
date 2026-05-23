"""
Tests for CRM Salesforce integration — Sprint 6, US-24 + US-43.

Structure:
  TestSalesforceClient  — unit tests, mock httpx + settings (no DB/network)
  TestCRMEndpoints      — integration tests, real test DB via conftest fixtures
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole


def auth(role: str) -> dict[str, str]:
    token = create_access_token(subject=str(uuid.uuid4()), role=role)
    return {"Authorization": f"Bearer {token}"}


async def seed_patient_and_doctor(test_db):
    patient_uuid = uuid.uuid4()
    doctor_uuid = uuid.uuid4()
    patient = Patient(
        patient_uuid=patient_uuid,
        consent_iot=False,
        consent_nlp=False,
        consent_sharing=False,
        sms_opt_out=False,
        birth_year=1985,
        sex="F",
        city_code="20000",
        chronic_conditions=[],
    )
    doctor = User(
        user_uuid=doctor_uuid,
        email=f"doctor-{doctor_uuid}@medisense.ai",
        hashed_password="hashed",
        role=UserRole.DOCTOR,
        first_name="Doc",
        last_name="Tor",
        is_active=True,
    )
    test_db.add(patient)
    test_db.add(doctor)
    await test_db.flush()
    return patient_uuid, doctor_uuid


async def seed_appointment(
    test_db,
    crm_sync_status: str = "PENDING",
    crm_retry_count: int = 0,
) -> uuid.UUID:
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment_uuid = uuid.uuid4()
    appt = Appointment(
        appointment_uuid=appointment_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        crm_sync_status=crm_sync_status,
        crm_retry_count=crm_retry_count,
    )
    test_db.add(appt)
    await test_db.flush()
    return appointment_uuid


# ── Unit tests: SalesforceClient ─────────────────────────────────────────────

class TestSalesforceClient:
    """
    Unit-level tests for app.services.salesforce_client.send_crm_event().

    All tests use mock httpx and mock settings — no DB or real network.
    Circuit breaker state is reset in setup_method for isolation.
    """

    def setup_method(self):
        import app.services.salesforce_client as sf
        sf._cb_failures = 0
        sf._cb_open_since = None

    def _make_settings(self, url="https://sf.example.com", token="tok", timeout=3.0):
        s = MagicMock()
        s.SALESFORCE_WEBHOOK_URL = url
        s.SALESFORCE_TOKEN = token
        s.SALESFORCE_TIMEOUT_SECONDS = timeout
        return s

    def _mock_http_response(self, status_code: int):
        resp = MagicMock()
        resp.status_code = status_code
        return resp

    def _mock_http_client(self, response):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        return mock_client

    async def test_send_success(self):
        """200 response → sent=True, correlation_id is a valid UUID4."""
        from app.services.salesforce_client import send_crm_event

        response = self._mock_http_response(200)
        mock_client = self._mock_http_client(response)
        settings = self._make_settings()

        with patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient", return_value=mock_client):
            result = await send_crm_event(
                patient_id="aaa",
                severity="urgent",
                appointment_id=None,
                specialist_type=None,
                query_fr="douleur thoracique",
                iot_triggered=False,
            )

        assert result.sent is True
        assert result.skipped is False
        assert result.cb_open is False
        # correlation_id must be a parseable UUID
        parsed = uuid.UUID(result.correlation_id)
        assert parsed.version == 4

    async def test_send_5xx_marks_failed(self):
        """500 response → sent=False, _cb_failures incremented."""
        import app.services.salesforce_client as sf
        from app.services.salesforce_client import send_crm_event

        response = self._mock_http_response(500)
        mock_client = self._mock_http_client(response)
        settings = self._make_settings()

        with patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient", return_value=mock_client):
            result = await send_crm_event(
                patient_id="aaa",
                severity="routine",
                appointment_id=None,
                specialist_type=None,
                query_fr="rendez-vous",
            )

        assert result.sent is False
        assert result.status_code == 500
        assert sf._cb_failures == 1

    async def test_skipped_when_no_url(self):
        """SALESFORCE_WEBHOOK_URL empty → skipped=True, no HTTP call."""
        from app.services.salesforce_client import send_crm_event

        settings = self._make_settings(url="")

        with patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient") as mock_cls:
            result = await send_crm_event(
                patient_id="aaa",
                severity="urgent",
                appointment_id=None,
                specialist_type=None,
                query_fr="test",
            )

        assert result.sent is False
        assert result.skipped is True
        mock_cls.assert_not_called()

    async def test_circuit_breaker_opens_after_threshold(self):
        """3 consecutive 500s → circuit opens → 4th call returns cb_open=True."""
        import app.services.salesforce_client as sf
        from app.services.salesforce_client import send_crm_event

        response = self._mock_http_response(500)
        mock_client = self._mock_http_client(response)
        settings = self._make_settings()

        with patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient", return_value=mock_client):
            for _ in range(3):
                await send_crm_event(
                    patient_id="aaa", severity="urgent",
                    appointment_id=None, specialist_type=None, query_fr="test",
                )

            assert sf._cb_open_since is not None

            # 4th request — circuit is open, must be rejected immediately
            fourth = await send_crm_event(
                patient_id="aaa", severity="urgent",
                appointment_id=None, specialist_type=None, query_fr="test",
            )

        assert fourth.cb_open is True
        assert fourth.sent is False

    async def test_persist_skips_when_db_is_none(self):
        """_persist_sync_result with db=None must not raise."""
        from app.services.salesforce_client import _persist_sync_result

        # Should complete silently without AttributeError
        await _persist_sync_result(None, None, "SENT", str(uuid.uuid4()), 0, None)
        await _persist_sync_result(None, str(uuid.uuid4()), "FAILED", str(uuid.uuid4()), 1, "err")

    async def test_persist_with_mock_db_sent(self):
        """_persist_sync_result with a real-ish mock db executes UPDATE and flush."""
        from app.services.salesforce_client import _persist_sync_result

        mock_db = AsyncMock()
        appt_id = str(uuid.uuid4())

        await _persist_sync_result(mock_db, appt_id, "SENT", str(uuid.uuid4()), 0, None)

        mock_db.execute.assert_awaited_once()
        mock_db.flush.assert_awaited_once()

    async def test_persist_with_mock_db_failed(self):
        """_persist_sync_result sets crm_synced_at=None for FAILED status."""
        from app.services.salesforce_client import _persist_sync_result

        mock_db = AsyncMock()
        appt_id = str(uuid.uuid4())

        await _persist_sync_result(mock_db, appt_id, "FAILED", str(uuid.uuid4()), 1, "HTTP 500")

        mock_db.execute.assert_awaited_once()
        mock_db.flush.assert_awaited_once()

    async def test_persist_swallows_db_exception(self):
        """_persist_sync_result must not propagate DB errors."""
        from app.services.salesforce_client import _persist_sync_result

        mock_db = AsyncMock()
        mock_db.execute.side_effect = RuntimeError("connection lost")
        appt_id = str(uuid.uuid4())

        # Should not raise
        await _persist_sync_result(mock_db, appt_id, "SENT", str(uuid.uuid4()), 0, None)

    async def test_send_network_error_marks_failed(self):
        """Network exception during POST → sent=False, failure counted."""
        import app.services.salesforce_client as sf
        from app.services.salesforce_client import send_crm_event

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        settings = self._make_settings()

        with patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient", return_value=mock_client):
            result = await send_crm_event(
                patient_id="aaa", severity="urgent",
                appointment_id=None, specialist_type=None, query_fr="test",
            )

        assert result.sent is False
        assert sf._cb_failures >= 1

    async def test_send_4xx_marks_failed_no_circuit_breaker(self):
        """401 response → sent=False, FAILED persisted, circuit breaker NOT opened."""
        import app.services.salesforce_client as sf
        from app.services.salesforce_client import send_crm_event

        response = self._mock_http_response(401)
        mock_client = self._mock_http_client(response)
        settings = self._make_settings()

        with patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient", return_value=mock_client):
            result = await send_crm_event(
                patient_id="aaa", severity="urgent",
                appointment_id=None, specialist_type=None, query_fr="test",
            )

        assert result.sent is False
        assert result.status_code == 401
        assert sf._cb_failures == 0  # 4xx must NOT increment circuit breaker

    async def test_send_info_severity_skips(self):
        """INFO severity → skipped immediately, no HTTP call."""
        from app.services.salesforce_client import send_crm_event

        settings = self._make_settings()

        with patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient") as mock_cls:
            result = await send_crm_event(
                patient_id="aaa", severity="info",
                appointment_id=None, specialist_type=None, query_fr="test",
            )

        assert result.skipped is True
        mock_cls.assert_not_called()

    async def test_circuit_breaker_resets_after_timeout(self):
        """CB half-open: after RESET_TIMEOUT_S elapsed, counters reset and request goes through."""
        import app.services.salesforce_client as sf
        from app.services.salesforce_client import send_crm_event, RESET_TIMEOUT_S

        sf._cb_open_since = 0.0
        sf._cb_failures = 3

        response = self._mock_http_response(200)
        mock_client = self._mock_http_client(response)
        settings = self._make_settings()

        with patch("app.services.salesforce_client.time.monotonic",
                   return_value=RESET_TIMEOUT_S + 1.0), \
             patch("app.services.salesforce_client.get_settings", return_value=settings), \
             patch("app.services.salesforce_client.httpx.AsyncClient", return_value=mock_client):
            result = await send_crm_event(
                patient_id="aaa", severity="urgent",
                appointment_id=None, specialist_type=None, query_fr="test",
            )

        assert result.sent is True
        assert sf._cb_open_since is None
        assert sf._cb_failures == 0


# ── Integration tests: CRM API endpoints ─────────────────────────────────────

class TestCRMEndpoints:
    """
    Integration tests for GET/PATCH/POST /api/v1/crm/tasks.

    Uses the real test DB (via conftest fixtures) and the ASGI test client.
    The mock_redis autouse fixture in conftest handles token blacklist checks.
    """

    async def test_list_requires_auth(self, client):
        """No bearer token → 403 (HTTPBearer raises 403 when header is absent)."""
        response = await client.get("/api/v1/crm/tasks")
        assert response.status_code == 403

    async def test_list_doctor_forbidden(self, client):
        """Doctor role is not authorized to access secretary-only CRM tasks."""
        response = await client.get(
            "/api/v1/crm/tasks",
            headers=auth("doctor"),
        )
        assert response.status_code == 403

    async def test_list_secretary_ok(self, client, test_db):
        """Secretary gets 200 and sees seeded appointment in items."""
        appt_uuid = await seed_appointment(test_db)

        response = await client.get("/api/v1/crm/tasks", headers=auth("secretary"))

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
        uuids = [item["appointment_uuid"] for item in data["items"]]
        assert str(appt_uuid) in uuids

    async def test_list_admin_ok(self, client, test_db):
        """Admin role is also allowed (same RBAC as secretary)."""
        await seed_appointment(test_db)
        response = await client.get("/api/v1/crm/tasks", headers=auth("admin"))
        assert response.status_code == 200

    async def test_list_filter_by_status(self, client, test_db):
        """?crm_sync_status= filter returns only matching appointments."""
        await seed_appointment(test_db, crm_sync_status="SENT")
        await seed_appointment(test_db, crm_sync_status="FAILED")

        response = await client.get(
            "/api/v1/crm/tasks?crm_sync_status=SENT",
            headers=auth("secretary"),
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["crm_sync_status"] == "SENT"

    async def test_patch_updates_salesforce_task_id(self, client, test_db):
        """PATCH updates salesforce_task_id on an existing appointment."""
        appt_uuid = await seed_appointment(test_db)

        response = await client.patch(
            f"/api/v1/crm/tasks/{appt_uuid}",
            json={"salesforce_task_id": "SF-001"},
            headers=auth("secretary"),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["salesforce_task_id"] == "SF-001"
        assert data["appointment_uuid"] == str(appt_uuid)

    async def test_patch_invalid_status_returns_422(self, client, test_db):
        """PATCH with unrecognized crm_sync_status → 422 validation error."""
        appt_uuid = await seed_appointment(test_db)

        response = await client.patch(
            f"/api/v1/crm/tasks/{appt_uuid}",
            json={"crm_sync_status": "INVALID_STATUS"},
            headers=auth("secretary"),
        )

        assert response.status_code == 422

    async def test_patch_not_found_404(self, client):
        """PATCH on unknown UUID → 404."""
        response = await client.patch(
            f"/api/v1/crm/tasks/{uuid.uuid4()}",
            json={"salesforce_task_id": "SF-XYZ"},
            headers=auth("secretary"),
        )
        assert response.status_code == 404

    async def test_retry_dispatches_async(self, client, test_db):
        """POST /retry dispatches asyncio.create_task and returns PENDING."""
        appt_uuid = await seed_appointment(test_db, crm_sync_status="FAILED")

        # side_effect closes the coroutine so pytest doesn't warn "never awaited"
        with patch("app.api.v1.endpoints.crm.asyncio.create_task",
                   side_effect=lambda coro: coro.close() or MagicMock()) as mock_create_task, \
             patch("app.api.v1.endpoints.crm.send_crm_event", new=AsyncMock()):
            response = await client.post(
                f"/api/v1/crm/tasks/{appt_uuid}/retry",
                json={"force": False},
                headers=auth("secretary"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["crm_sync_status"] == "PENDING"
        assert "Retry dispatched" in data["message"]
        mock_create_task.assert_called_once()

    async def test_retry_sent_without_force_returns_409(self, client, test_db):
        """Retrying a SENT task without force=True → 409 Conflict."""
        appt_uuid = await seed_appointment(test_db, crm_sync_status="SENT")

        response = await client.post(
            f"/api/v1/crm/tasks/{appt_uuid}/retry",
            json={"force": False},
            headers=auth("secretary"),
        )

        assert response.status_code == 409

    async def test_retry_sent_with_force_succeeds(self, client, test_db):
        """Retrying a SENT task WITH force=True → 200, dispatch proceeds."""
        appt_uuid = await seed_appointment(test_db, crm_sync_status="SENT")

        with patch("app.api.v1.endpoints.crm.asyncio.create_task",
                   side_effect=lambda coro: coro.close() or MagicMock()), \
             patch("app.api.v1.endpoints.crm.send_crm_event", new=AsyncMock()):
            response = await client.post(
                f"/api/v1/crm/tasks/{appt_uuid}/retry",
                json={"force": True},
                headers=auth("secretary"),
            )

        assert response.status_code == 200

    async def test_retry_max_retries_exceeded_returns_429(self, client, test_db):
        """When crm_retry_count >= SALESFORCE_MAX_RETRIES → 429."""
        from app.core.config import get_settings
        max_retries = get_settings().SALESFORCE_MAX_RETRIES
        appt_uuid = await seed_appointment(
            test_db, crm_sync_status="FAILED", crm_retry_count=max_retries
        )

        response = await client.post(
            f"/api/v1/crm/tasks/{appt_uuid}/retry",
            json={"force": False},
            headers=auth("secretary"),
        )

        assert response.status_code == 429

    async def test_retry_not_found_404(self, client):
        """POST /retry on unknown UUID → 404."""
        response = await client.post(
            f"/api/v1/crm/tasks/{uuid.uuid4()}/retry",
            json={"force": False},
            headers=auth("secretary"),
        )
        assert response.status_code == 404


# ── D1: POST /crm/sms/send/{appointment_uuid} ────────────────────────────────


class TestCrmSmsSend:
    @staticmethod
    def _patch_send_path(phone: str = "+212600000001"):
        """Mock SMS provider + FCM so tests don't need pgcrypto/Firebase creds."""
        return (
            patch("app.api.v1.endpoints.crm._get_patient_phone_number",
                  AsyncMock(return_value=phone)),
            patch("app.api.v1.endpoints.crm._send_sms",
                  AsyncMock(return_value="mock-id")),
            patch("app.api.v1.endpoints.crm.send_to_tokens",
                  AsyncMock(return_value=1)),
        )

    async def test_sms_send_happy_dispatches_and_bumps_counter(self, client, test_db):
        """
        Happy path must actually dispatch (status=sent) and bump
        appointment.sms_reminders_sent so the agenda counter moves —
        the regression we just fixed.
        """
        from sqlalchemy import select
        appt_uuid = await seed_appointment(test_db)

        phone_p, sms_p, push_p = self._patch_send_path()
        with phone_p, sms_p as sms_mock, push_p as push_mock:
            response = await client.post(
                f"/api/v1/crm/sms/send/{appt_uuid}",
                headers=auth("secretary"),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "sent"
        assert sms_mock.await_count == 1
        assert push_mock.await_count == 1

        test_db.expire_all()
        bumped = (
            await test_db.execute(
                select(Appointment.sms_reminders_sent).where(
                    Appointment.appointment_uuid == appt_uuid
                )
            )
        ).scalar_one()
        assert bumped == 1

    async def test_sms_send_pushes_when_phone_missing(self, client, test_db):
        """No phone on file but FCM tokens present → still succeeds via push."""
        appt_uuid = await seed_appointment(test_db)
        with (
            patch("app.api.v1.endpoints.crm._get_patient_phone_number",
                  AsyncMock(return_value=None)),
            patch("app.api.v1.endpoints.crm._send_sms",
                  AsyncMock(return_value="mock-id")) as sms_mock,
            patch("app.api.v1.endpoints.crm.send_to_tokens",
                  AsyncMock(return_value=1)) as push_mock,
        ):
            response = await client.post(
                f"/api/v1/crm/sms/send/{appt_uuid}",
                headers=auth("secretary"),
            )
        assert response.status_code == 200
        assert response.json()["status"] == "sent"
        assert sms_mock.await_count == 0
        assert push_mock.await_count == 1

    async def test_sms_send_502_when_both_channels_fail(self, client, test_db):
        appt_uuid = await seed_appointment(test_db)
        with (
            patch("app.api.v1.endpoints.crm._get_patient_phone_number",
                  AsyncMock(return_value=None)),
            patch("app.api.v1.endpoints.crm.send_to_tokens",
                  AsyncMock(return_value=0)),
        ):
            response = await client.post(
                f"/api/v1/crm/sms/send/{appt_uuid}",
                headers=auth("secretary"),
            )
        assert response.status_code == 502

    async def test_sms_send_idempotent_same_day(self, client, test_db):
        appt_uuid = await seed_appointment(test_db)
        phone_p, sms_p, push_p = self._patch_send_path()
        with phone_p, sms_p, push_p:
            r1 = await client.post(
                f"/api/v1/crm/sms/send/{appt_uuid}",
                headers=auth("secretary"),
            )
            r2 = await client.post(
                f"/api/v1/crm/sms/send/{appt_uuid}",
                headers=auth("secretary"),
            )
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]
        assert r2.json()["status"] == "sent"

    async def test_sms_send_no_auth_403(self, client):
        response = await client.post(f"/api/v1/crm/sms/send/{uuid.uuid4()}")
        assert response.status_code == 403

    async def test_sms_send_unknown_appointment_404(self, client):
        response = await client.post(
            f"/api/v1/crm/sms/send/{uuid.uuid4()}",
            headers=auth("secretary"),
        )
        assert response.status_code == 404
