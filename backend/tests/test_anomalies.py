"""
Tests for POST /api/v1/anomalies/detect and GET /api/v1/anomalies/recent/{uuid}.
Coverage targets: anomalies.py endpoint + anomaly_detector service + lstm_anomaly_service unit paths.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_access_token


def doctor_headers() -> dict[str, str]:
    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    return {"Authorization": f"Bearer {token}"}


def patient_headers() -> dict[str, str]:
    token = create_access_token(subject=str(uuid.uuid4()), role="patient")
    return {"Authorization": f"Bearer {token}"}


VALID_VITALS = [
    {"hr": 72.0, "spo2": 98.0, "hrv": 42.0, "temperature": 36.6},
    {"hr": 74.0, "spo2": 97.0, "hrv": 40.0, "temperature": 36.7},
    {"hr": 70.0, "spo2": 98.0, "hrv": 44.0, "temperature": 36.5},
]


# ── POST /anomalies/detect ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_detect_no_auth_403(client):
    r = await client.post("/api/v1/anomalies/detect", json={
        "patient_uuid": str(uuid.uuid4()),
        "vitals": VALID_VITALS,
    })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_detect_patient_role_403(client):
    r = await client.post(
        "/api/v1/anomalies/detect",
        json={"patient_uuid": str(uuid.uuid4()), "vitals": VALID_VITALS},
        headers=patient_headers(),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_detect_invalid_uuid_422(client):
    r = await client.post(
        "/api/v1/anomalies/detect",
        json={"patient_uuid": "not-a-uuid", "vitals": VALID_VITALS},
        headers=doctor_headers(),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_detect_empty_vitals_422(client):
    r = await client.post(
        "/api/v1/anomalies/detect",
        json={"patient_uuid": str(uuid.uuid4()), "vitals": []},
        headers=doctor_headers(),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_detect_returns_score(client):
    mock_result = {
        "score_5m": 0.0,
        "score_60m": None,
        "alert_critical": False,
        "trend_elevated": False,
    }
    with patch(
        "app.api.v1.endpoints.anomalies.ingest_reading",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        r = await client.post(
            "/api/v1/anomalies/detect",
            json={"patient_uuid": str(uuid.uuid4()), "vitals": VALID_VITALS},
            headers=doctor_headers(),
        )
    assert r.status_code == 200
    data = r.json()
    assert "score_5m" in data
    assert "alert_critical" in data
    assert data["alert_critical"] is False


@pytest.mark.asyncio
async def test_detect_critical_anomaly(client):
    mock_result = {
        "score_5m": 0.92,
        "score_60m": 0.75,
        "alert_critical": True,
        "trend_elevated": True,
    }
    with patch(
        "app.api.v1.endpoints.anomalies.ingest_reading",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        r = await client.post(
            "/api/v1/anomalies/detect",
            json={"patient_uuid": str(uuid.uuid4()), "vitals": VALID_VITALS},
            headers=doctor_headers(),
        )
    assert r.status_code == 200
    data = r.json()
    assert data["alert_critical"] is True
    assert data["trend_elevated"] is True


# ── GET /anomalies/recent/{uuid} ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_recent_no_auth_403(client):
    r = await client.get(f"/api/v1/anomalies/recent/{uuid.uuid4()}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_recent_invalid_uuid_422(client):
    r = await client.get(
        "/api/v1/anomalies/recent/not-a-uuid",
        headers=doctor_headers(),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_recent_returns_scores(client):
    patient_uuid = str(uuid.uuid4())
    mock_scores = {
        "patient_uuid": patient_uuid,
        "score_5m": 0.12,
        "score_60m": 0.08,
        "readings_5m": 10,
        "readings_60m": 45,
        "alert_critical": False,
        "trend_elevated": False,
    }
    with patch(
        "app.api.v1.endpoints.anomalies.get_recent_scores",
        new_callable=AsyncMock,
        return_value=mock_scores,
    ):
        r = await client.get(
            f"/api/v1/anomalies/recent/{patient_uuid}",
            headers=doctor_headers(),
        )
    assert r.status_code == 200
    data = r.json()
    assert data["patient_uuid"] == patient_uuid
    assert data["score_5m"] == pytest.approx(0.12)
    assert data["alert_critical"] is False
