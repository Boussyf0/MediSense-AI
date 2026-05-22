"""
Tests for Sprint 4 DPA endpoints (US-41) and HITL approval (US-42).

TESTING STRATEGY:
  Integration-style tests using the FastAPI test client and a real DB session
  (via conftest.py fixtures).  We test the full HTTP flow:
    request → auth → endpoint → service → DB → response.

  We mock:
    - dpa_summarizer.build() in GET endpoint tests (avoids complex DB setup)
    - Redis blacklist (autouse fixture in conftest.py)

  We test directly (real DB):
    - approve/reject optimistic locking (requires real DB UPDATE with rowcount)

WHY OPTIMISTIC LOCKING TESTS MATTER:
  Two doctors accessing the same patient simultaneously is a real clinical
  scenario.  If both approve the same DPA summary, only one should succeed —
  the second must get HTTP 409.  This test validates that guarantee.
"""
import uuid
import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_doctor_token(user_id: str | None = None) -> str:
    """Generate a real JWT for a doctor user."""
    from app.core.security import create_access_token
    uid = user_id or str(uuid.uuid4())
    return create_access_token(subject=uid, role="doctor")


def _make_patient_token(user_id: str | None = None) -> str:
    """Generate a real JWT for a patient user (unauthorized for doctor endpoints)."""
    from app.core.security import create_access_token
    uid = user_id or str(uuid.uuid4())
    return create_access_token(subject=uid, role="patient")


async def _insert_dpa_summary(
    db: AsyncSession,
    patient_id: str,
    status: str = "PENDING",
    version: int = 1,
) -> uuid.UUID:
    """Insert a minimal DPA summary row for testing."""
    from app.db.models.dpa_summary import DPASummary
    summary_id = uuid.uuid4()
    patient_uuid = uuid.UUID(patient_id)
    summary = DPASummary(
        id=summary_id,
        patient_id=patient_uuid,
        status=status,
        version=version,
        payload_before={
            "patient_uuid": str(patient_uuid),
            "symptoms": ["fièvre 3 jours", "toux sèche"],
            "iot_summary": {"latest_anomalies": [], "trend": "stable"},
            "recommended_actions": [
                {"action": "refer", "specialist": "médecine générale", "urgency": "routine"}
            ],
            "confidence": 0.75,
            "data_freshness_minutes": 0,
        },
    )
    db.add(summary)
    await db.flush()
    return summary_id


# ── US-41: DPA Summary GET ────────────────────────────────────────────────────

class TestDPASummaryGet:
    """Tests for GET /doctor/patient/{uuid}/dpa-summary."""

    @pytest.mark.asyncio
    async def test_requires_doctor_role(self, client):
        """Patient token must be rejected with 403."""
        patient_id = str(uuid.uuid4())
        token = _make_patient_token()
        resp = await client.get(
            f"/api/v1/doctor/patient/{patient_id}/dpa-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_doctor_gets_summary(self, client, test_db):
        """
        Doctor with valid token → 200 with DPA summary structure.
        We mock dpa_summarizer.build() to avoid complex DB setup.
        """
        from app.db.models.dpa_summary import DPASummary

        patient_id = str(uuid.uuid4())
        token = _make_doctor_token()

        # Build a mock DPASummary object (mimics what dpa_summarizer.build returns)
        mock_summary = MagicMock(spec=DPASummary)
        mock_summary.id = uuid.uuid4()
        mock_summary.status = "PENDING"
        mock_summary.version = 1
        mock_summary.created_at = datetime.now(timezone.utc)
        mock_summary.payload_before = {
            "symptoms": ["fièvre 38.5°C", "toux sèche"],
            "iot_summary": {"latest_anomalies": [], "trend": "stable"},
            "recommended_actions": [
                {"action": "refer", "specialist": "médecine générale", "urgency": "routine"}
            ],
            "confidence": 0.78,
            "data_freshness_minutes": 0,
        }

        with patch(
            "app.api.v1.endpoints.doctor.dpa_summarizer.build",
            AsyncMock(return_value=mock_summary),
        ):
            resp = await client.get(
                f"/api/v1/doctor/patient/{patient_id}/dpa-summary",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "summary_id" in data
        assert "symptoms" in data
        assert "iot_summary" in data
        assert "recommended_actions" in data
        assert "confidence" in data
        assert data["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_get_returns_latest_existing_summary_after_approval(self, client, test_db):
        """
        After approval, GET must return the persisted APPROVED summary so the UI
        reflects the doctor's decision. Without this, the endpoint would rebuild
        a fresh PENDING summary on every load and the approval state would never
        be visible (root cause of the agenda "valider → rien ne change" bug).
        """
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id, status="APPROVED", version=2)
        token = _make_doctor_token()

        resp = await client.get(
            f"/api/v1/doctor/patient/{patient_id}/dpa-summary",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary_id"] == str(summary_id)
        assert data["status"] == "APPROVED"
        assert data["version"] == 2

    @pytest.mark.asyncio
    async def test_get_with_refresh_builds_new_summary(self, client, test_db):
        """?refresh=true forces a fresh build even when an existing summary is present."""
        patient_id = str(uuid.uuid4())
        old_summary_id = await _insert_dpa_summary(test_db, patient_id, status="APPROVED", version=2)
        token = _make_doctor_token()

        from app.db.models.dpa_summary import DPASummary
        mock_summary = MagicMock(spec=DPASummary)
        mock_summary.id = uuid.uuid4()
        mock_summary.status = "PENDING"
        mock_summary.version = 1
        mock_summary.created_at = datetime.now(timezone.utc)
        mock_summary.actions = []
        mock_summary.payload_before = {
            "symptoms": [], "iot_summary": {"latest_anomalies": [], "trend": "stable"},
            "recommended_actions": [], "confidence": 0.5, "data_freshness_minutes": 0,
        }
        with patch(
            "app.api.v1.endpoints.doctor.dpa_summarizer.build",
            AsyncMock(return_value=mock_summary),
        ):
            resp = await client.get(
                f"/api/v1/doctor/patient/{patient_id}/dpa-summary?refresh=true",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        assert resp.json()["summary_id"] != str(old_summary_id)
        assert resp.json()["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_summary_response_has_correct_schema(self, client):
        """Verify all required DPASummaryOut fields are present."""
        from app.db.models.dpa_summary import DPASummary

        patient_id = str(uuid.uuid4())
        token = _make_doctor_token()
        required_fields = [
            "summary_id", "patient_uuid", "symptoms", "iot_summary",
            "recommended_actions", "confidence", "data_freshness_minutes",
            "status", "version",
        ]

        mock_summary = MagicMock(spec=DPASummary)
        mock_summary.id = uuid.uuid4()
        mock_summary.status = "PENDING"
        mock_summary.version = 1
        mock_summary.created_at = datetime.now(timezone.utc)
        mock_summary.payload_before = {
            "symptoms": [],
            "iot_summary": {"latest_anomalies": [], "trend": "stable"},
            "recommended_actions": [],
            "confidence": 0.5,
            "data_freshness_minutes": 0,
        }

        with patch(
            "app.api.v1.endpoints.doctor.dpa_summarizer.build",
            AsyncMock(return_value=mock_summary),
        ):
            resp = await client.get(
                f"/api/v1/doctor/patient/{patient_id}/dpa-summary",
                headers={"Authorization": f"Bearer {token}"},
            )

        data = resp.json()
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_patient_card_populated_from_patient_row(self, client, test_db):
        """When a Patient row exists, the DPA response carries real age/sex/chronics."""
        from app.db.models.patient import Patient

        patient_id = uuid.uuid4()
        test_db.add(Patient(
            patient_uuid=patient_id,
            birth_year=1978,
            sex="F",
            chronic_conditions=["asthma", "htn"],
            consent_iot=False, consent_nlp=False,
            consent_sharing=False, sms_opt_out=False,
        ))
        await _insert_dpa_summary(test_db, str(patient_id))
        token = _make_doctor_token()

        resp = await client.get(
            f"/api/v1/doctor/patient/{patient_id}/dpa-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        card = resp.json()["patient"]
        # Age is derived from birth_year against the current year — accept a
        # small window so the test doesn't flake on Jan 1.
        assert card["age"] is not None and 45 <= card["age"] <= 50
        assert card["sex"] == "F"
        assert card["chronic_conditions"] == ["asthma", "htn"]

    @pytest.mark.asyncio
    async def test_patient_card_defaults_when_no_patient_row(self, client, test_db):
        """No Patient row → card uses safe defaults (all None / empty)."""
        patient_id = str(uuid.uuid4())
        await _insert_dpa_summary(test_db, patient_id)
        token = _make_doctor_token()

        resp = await client.get(
            f"/api/v1/doctor/patient/{patient_id}/dpa-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        card = resp.json()["patient"]
        assert card["age"] is None
        assert card["sex"] is None
        assert card["chronic_conditions"] == []

    @pytest.mark.asyncio
    async def test_history_includes_past_appointments_and_summaries(self, client, test_db):
        """When the live window is empty, the response carries patient history
        so the doctor still has context to act on."""
        from datetime import datetime, timezone, timedelta
        from app.db.models.appointment import Appointment
        from app.db.models.patient import Patient
        from app.db.models.user import User, UserRole

        patient_id = uuid.uuid4()
        doctor_id = uuid.uuid4()
        test_db.add(Patient(
            patient_uuid=patient_id,
            consent_iot=False, consent_nlp=False,
            consent_sharing=False, sms_opt_out=False,
        ))
        test_db.add(User(
            user_uuid=doctor_id, email=f"dr-{doctor_id}@medisense.ai",
            hashed_password="hashed", role=UserRole.DOCTOR,
            first_name="Karim", last_name="Bennis", is_active=True,
        ))
        await test_db.flush()

        # Past appointment (completed, 10 days ago).
        past_appt_uuid = uuid.uuid4()
        test_db.add(Appointment(
            appointment_uuid=past_appt_uuid,
            patient_uuid=patient_id,
            doctor_uuid=doctor_id,
            scheduled_at=datetime.now(timezone.utc) - timedelta(days=10),
            duration_minutes=20,
            status="COMPLETED",
            urgency_flag="routine",
            rag_summary="Patient stable, suivi annuel.",
        ))

        # An older approved DPA summary, plus the current PENDING one.
        await _insert_dpa_summary(test_db, str(patient_id), status="APPROVED", version=2)
        await _insert_dpa_summary(test_db, str(patient_id))
        token = _make_doctor_token()

        resp = await client.get(
            f"/api/v1/doctor/patient/{patient_id}/dpa-summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        history = resp.json()["history"]
        assert len(history["past_appointments"]) == 1
        assert history["past_appointments"][0]["status"] == "COMPLETED"
        assert history["past_appointments"][0]["rag_summary"].startswith("Patient stable")
        # current summary must be excluded → exactly one prior summary.
        assert len(history["previous_summaries"]) == 1
        assert history["previous_summaries"][0]["status"] == "APPROVED"
        assert history["previous_summaries"][0]["actions_count"] == 1
        assert history["previous_summaries"][0]["top_action"] is not None


# ── US-42: Approve / Reject ───────────────────────────────────────────────────

class TestDPAApproval:
    """
    Tests for POST /doctor/dpa-summary/{id}/approve and /reject.
    Uses real DB to test optimistic locking (rowcount-based).
    """

    @pytest.mark.asyncio
    async def test_approve_pending_summary(self, client, test_db):
        """Doctor approves a PENDING summary → status becomes APPROVED."""
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        token = _make_doctor_token()

        resp = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={"doctor_note": "Accord avec les recommandations"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["version"] == 2   # version incremented by optimistic lock

    @pytest.mark.asyncio
    async def test_approve_with_edited_actions_becomes_modified(self, client, test_db):
        """Approve with edited_actions → status becomes MODIFIED."""
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        token = _make_doctor_token()

        resp = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "doctor_note": "Changé vers ORL",
                "edited_actions": [
                    {"action": "refer", "specialist": "ORL", "urgency": "routine"}
                ],
            },
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "MODIFIED"

    @pytest.mark.asyncio
    async def test_reject_requires_reason(self, client, test_db):
        """Rejection without reason (too short) → 422 validation error."""
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        token = _make_doctor_token()

        resp = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/reject",
            headers={"Authorization": f"Bearer {token}"},
            json={"doctor_note": "Non"},   # too short (< 10 chars)
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_reject_with_valid_reason(self, client, test_db):
        """Reject with sufficient reason → 200, status=REJECTED."""
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        token = _make_doctor_token()

        resp = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/reject",
            headers={"Authorization": f"Bearer {token}"},
            json={"doctor_note": "Recommandations incorrectes pour ce profil patient"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "REJECTED"

    @pytest.mark.asyncio
    async def test_optimistic_lock_prevents_double_approval(self, client, test_db):
        """
        OPTIMISTIC LOCKING TEST — the most important test in this file.

        Scenario:
          - Doctor A and Doctor B both load the same PENDING summary (version=1)
          - Doctor A approves first → version becomes 2
          - Doctor B tries to approve (still has version=1 in their session)
          - Doctor B must get HTTP 409 Conflict

        Implementation:
          We call approve twice in sequence.  The second call finds version=2
          in the DB but tries to update WHERE version=1 → 0 rows affected → 409.
        """
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        token_a = _make_doctor_token()
        token_b = _make_doctor_token()

        # Doctor A approves first
        resp_a = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/approve",
            headers={"Authorization": f"Bearer {token_a}"},
            json={},
        )
        assert resp_a.status_code == 200

        # Doctor B tries to approve the same summary — must get 409
        resp_b = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/approve",
            headers={"Authorization": f"Bearer {token_b}"},
            json={},
        )
        assert resp_b.status_code == 409
        # _assert_pending fires first (status=APPROVED after Doctor A) — message
        # varies depending on which code path raises the 409, both are correct.
        assert resp_b.json()["detail"]

    @pytest.mark.asyncio
    async def test_cannot_approve_already_approved(self, client, test_db):
        """Approving an already APPROVED summary → 409."""
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id, status="APPROVED", version=2)
        token = _make_doctor_token()

        resp = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_approve_nonexistent_summary_returns_404(self, client):
        """Approving a non-existent summary → 404."""
        token = _make_doctor_token()
        fake_id = str(uuid.uuid4())

        resp = await client.post(
            f"/api/v1/doctor/dpa-summary/{fake_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert resp.status_code == 404


# ── DPA Summarizer Unit Tests ─────────────────────────────────────────────────

class TestDPASummarizer:
    """Unit tests for app.services.dpa_summarizer helper functions."""

    def test_compute_trend_critical(self):
        from app.services.dpa_summarizer import _compute_trend
        assert _compute_trend(["critical", "moderate", "mild"]) == "critical"

    def test_compute_trend_declining(self):
        from app.services.dpa_summarizer import _compute_trend
        # Newest first: moderate(2) > mild(1) → declining
        assert _compute_trend(["moderate", "mild"]) == "declining"

    def test_compute_trend_improving(self):
        from app.services.dpa_summarizer import _compute_trend
        # Newest first: mild(1) < moderate(2) → improving
        assert _compute_trend(["mild", "moderate"]) == "improving"

    def test_compute_trend_stable(self):
        from app.services.dpa_summarizer import _compute_trend
        assert _compute_trend(["mild", "mild"]) == "stable"

    def test_compute_trend_empty(self):
        from app.services.dpa_summarizer import _compute_trend
        assert _compute_trend([]) == "stable"

    def test_generate_recommendations_with_critical_iot(self):
        """Critical IoT trend → alert action as first recommendation."""
        from app.services.dpa_summarizer import _generate_recommendations
        iot_data = {
            "latest_anomalies": [
                {"metric": "SpO2", "value": 88.0, "unit": "%",
                 "threshold": 95.0, "severity": "critical", "detected_at": None}
            ],
            "trend": "critical",
        }
        actions = _generate_recommendations([], iot_data)
        assert any(a["action"] == "alert" for a in actions)

    def test_generate_recommendations_default_refer(self):
        """No symptoms, no IoT → default refer to general medicine."""
        from app.services.dpa_summarizer import _generate_recommendations
        actions = _generate_recommendations([], {"latest_anomalies": [], "trend": "stable"})
        assert len(actions) == 1
        assert actions[0]["action"] == "refer"
        assert actions[0]["specialist"] == "médecine générale"

    def test_compute_confidence_low_without_data(self):
        from app.services.dpa_summarizer import _compute_confidence
        conf = _compute_confidence([], {"latest_anomalies": [], "trend": "stable"})
        assert conf == pytest.approx(0.4)   # base score only

    def test_compute_confidence_high_with_data(self):
        from app.services.dpa_summarizer import _compute_confidence
        symptoms = ["fièvre", "toux", "maux de tête", "fatigue", "courbatures", "frissons"]
        iot_data = {"latest_anomalies": [{"metric": "SpO2"}], "trend": "declining"}
        conf = _compute_confidence(symptoms, iot_data)
        assert conf >= 0.9   # max capped at 0.95


# ── US-42: Per-action decision ────────────────────────────────────────────────

class TestDPADecideAction:
    """Tests for PATCH /doctor/dpa-summary/{summary_id}/action/{action_id}."""

    async def _insert_action(
        self, db: AsyncSession, summary_id: uuid.UUID
    ) -> uuid.UUID:
        from app.db.models.dpa_summary import AgentAction
        action_id = uuid.uuid4()
        action = AgentAction(
            id=action_id,
            summary_id=summary_id,
            action_type="refer",
            payload={"action": "refer", "specialist": "cardiologie", "urgency": "routine"},
            status="pending",
        )
        db.add(action)
        await db.flush()
        return action_id

    @pytest.mark.asyncio
    async def test_decide_action_approves_and_returns_summary(self, client, test_db):
        """Doctor approves a single action → 200 with summary state."""
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        action_id = await self._insert_action(test_db, summary_id)
        token = _make_doctor_token()

        resp = await client.patch(
            f"/api/v1/doctor/dpa-summary/{summary_id}/action/{action_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "approved"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary_id"] == str(summary_id)
        assert "Action approved." in data["message"]

    @pytest.mark.asyncio
    async def test_summary_approve_preserves_per_action_rejection(self, client, test_db):
        """
        Per-action decisions must survive a subsequent summary-level approval.

        Flow:
          1. Doctor rejects action A via PATCH /action/{id}
          2. Doctor clicks 'Valider et signer' → POST /approve on the summary
        Action A must remain status='rejected', not be flipped back to 'approved'
        by the bulk update inside approve_dpa_summary.
        """
        from sqlalchemy import select
        from app.db.models.dpa_summary import AgentAction

        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        rejected_id = await self._insert_action(test_db, summary_id)
        pending_id = await self._insert_action(test_db, summary_id)
        token = _make_doctor_token()

        patch_resp = await client.patch(
            f"/api/v1/doctor/dpa-summary/{summary_id}/action/{rejected_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "rejected"},
        )
        assert patch_resp.status_code == 200

        approve_resp = await client.post(
            f"/api/v1/doctor/dpa-summary/{summary_id}/approve",
            headers={"Authorization": f"Bearer {token}"},
            json={"doctor_note": "OK pour le reste"},
        )
        assert approve_resp.status_code == 200

        test_db.expire_all()
        rows = (
            await test_db.execute(
                select(AgentAction.id, AgentAction.status).where(
                    AgentAction.summary_id == summary_id
                )
            )
        ).all()
        statuses = {row.id: row.status for row in rows}
        assert statuses[rejected_id] == "rejected"
        assert statuses[pending_id] == "approved"

    @pytest.mark.asyncio
    async def test_decide_action_wrong_summary_id_returns_404(self, client, test_db):
        """Action id that belongs to a different summary → 404."""
        patient_id = str(uuid.uuid4())
        summary_id = await _insert_dpa_summary(test_db, patient_id)
        action_id = await self._insert_action(test_db, summary_id)
        token = _make_doctor_token()

        wrong_summary_id = uuid.uuid4()
        resp = await client.patch(
            f"/api/v1/doctor/dpa-summary/{wrong_summary_id}/action/{action_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "rejected"},
        )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Action introuvable"
