"""
Tests for POST /api/v1/anomalies/detect, GET /api/v1/anomalies/recent/{uuid},
and GET /api/v1/anomalies/summary.
Coverage targets: anomalies.py endpoint + anomaly_detector service + lstm_anomaly_service unit paths.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_access_token
from app.db.models.biometric_reading import BiometricReading
from app.db.models.patient import Patient


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


# ── GET /anomalies/summary ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_no_auth_403(client):
    r = await client.get("/api/v1/anomalies/summary")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_summary_doctor_role_403(client):
    r = await client.get(
        "/api/v1/anomalies/summary",
        headers=doctor_headers(),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_summary_no_data_returns_friendly_message(client, test_db):
    patient_uuid = uuid.uuid4()
    test_db.add(Patient(patient_uuid=patient_uuid, consent_iot=True))
    await test_db.flush()
    token = create_access_token(subject=str(patient_uuid), role="patient")

    r = await client.get(
        "/api/v1/anomalies/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["sample_count"] == 0
    assert data["hrv_trend_pct"] is None
    assert "Synchronisez" in data["summary"]


@pytest.mark.asyncio
async def test_summary_with_readings_computes_trend(client, test_db):
    patient_uuid = uuid.uuid4()
    test_db.add(Patient(patient_uuid=patient_uuid, consent_iot=True))
    await test_db.flush()

    now = datetime.now(timezone.utc)
    # Prior 6 days: high HRV ~50; last 24h: low HRV ~30 → trend down ~-40%
    for i in range(48):
        test_db.add(BiometricReading(
            patient_uuid=patient_uuid,
            ts=now - timedelta(hours=24 + i),
            hr=72, spo2=98, hrv=50,
        ))
    for i in range(12):
        test_db.add(BiometricReading(
            patient_uuid=patient_uuid,
            ts=now - timedelta(hours=i),
            hr=72, spo2=98, hrv=30,
        ))
    await test_db.flush()

    token = create_access_token(subject=str(patient_uuid), role="patient")
    r = await client.get(
        "/api/v1/anomalies/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["sample_count"] == 60
    assert data["hrv_trend_pct"] is not None
    assert data["hrv_trend_pct"] < -10
    assert "HRV" in data["summary"]
