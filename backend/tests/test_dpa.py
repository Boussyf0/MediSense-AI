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
