"""Tests for the predict endpoints (no-show + feedback)."""
import uuid
import pytest
from unittest.mock import patch

from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_predict_noshow_returns_prediction(client):
    """POST /predict/noshow returns prediction when model is ready."""
    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    mock_result = {
        "noshow_probability": 0.35,
        "risk_color": "orange",
        "shap_contributions": {"age": 0.1, "distance_to_clinic": 0.2},
        "model_version": "v1.0",
    }
    with patch("app.api.v1.endpoints.predict.noshow_predictor") as mp:
        mp.predict.return_value = mock_result
        resp = await client.post(
            "/api/v1/predict/noshow",
            json={
                "age": 45, "sex": "M", "distance_to_clinic": 5.0,
                "weather_score": 0.7, "previous_noshows": 2,
                "days_since_booking": 3, "day_of_week": 1,
                "appointment_hour": 10, "chronic_conditions_count": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["risk_color"] == "orange"


@pytest.mark.asyncio
async def test_predict_noshow_model_not_ready(client):
    """POST /predict/noshow returns 503 when model not loaded."""
    from app.services.noshow_predictor import ModelNotReadyError

    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    with patch("app.api.v1.endpoints.predict.noshow_predictor") as mp:
        mp.predict.side_effect = ModelNotReadyError("not loaded")
        resp = await client.post(
            "/api/v1/predict/noshow",
            json={
                "age": 45, "sex": "M", "distance_to_clinic": 5.0,
                "weather_score": 0.7, "previous_noshows": 2,
                "days_since_booking": 3, "day_of_week": 1,
                "appointment_hour": 10, "chronic_conditions_count": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_predict_noshow_no_auth_returns_403(client):
    resp = await client.post("/api/v1/predict/noshow", json={
        "age": 45, "sex": "M", "distance_to_clinic": 5.0,
        "weather_score": 0.7, "previous_noshows": 2,
        "days_since_booking": 3, "day_of_week": 1,
        "appointment_hour": 10, "chronic_conditions_count": 1,
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_predict_noshow_validation_error(client):
    """POST /predict/noshow returns 422 on feature validation error."""
    from app.services.noshow_predictor import FeatureValidationError

    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    with patch("app.api.v1.endpoints.predict.noshow_predictor") as mp:
        mp.predict.side_effect = FeatureValidationError("bad features")
        resp = await client.post(
            "/api/v1/predict/noshow",
            json={
                "age": 45, "sex": "M", "distance_to_clinic": 5.0,
                "weather_score": 0.7, "previous_noshows": 2,
                "days_since_booking": 3, "day_of_week": 1,
                "appointment_hour": 10, "chronic_conditions_count": 1,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feedback_appointment_not_found(client):
    """POST /predict/feedback returns 404 for unknown appointment."""
    token = create_access_token(subject=str(uuid.uuid4()), role="secretary")
    resp = await client.post(
        "/api/v1/predict/feedback",
        json={
            "appointment_uuid": str(uuid.uuid4()),
            "actual_status": "COMPLETED",
            "was_predicted_correctly": True,
            "prediction_prob": 0.1,
            "model_version": "v1.0",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_no_auth_returns_403(client):
    resp = await client.post("/api/v1/predict/feedback", json={
        "appointment_uuid": str(uuid.uuid4()),
        "actual_status": "NO_SHOW",
        "was_predicted_correctly": False,
        "prediction_prob": 0.8,
        "model_version": "v1.0",
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_feedback_happy_path(client, test_db):
    """POST /predict/feedback saves feedback for an existing appointment."""
    from datetime import datetime, timezone
    from app.db.models.appointment import Appointment
    from app.db.models.patient import Patient
    from app.db.models.user import User, UserRole
    from app.core.security import hash_password

    # Seed a doctor and patient
    doc_uuid = uuid.uuid4()
    pat_uuid = uuid.uuid4()
    doctor = User(user_uuid=doc_uuid, email="doc@test.com", first_name="Dr",
                  last_name="Test", role=UserRole.DOCTOR,
                  hashed_password=hash_password("pass"))
    patient = Patient(patient_uuid=pat_uuid, birth_year=1990, sex="M")
    test_db.add_all([doctor, patient])
    await test_db.flush()

    appt_uuid = uuid.uuid4()
    appt = Appointment(
        appointment_uuid=appt_uuid,
        patient_uuid=pat_uuid,
        doctor_uuid=doc_uuid,
        scheduled_at=datetime.now(timezone.utc),
        status="COMPLETED",
    )
    test_db.add(appt)
    await test_db.flush()

    token = create_access_token(subject=str(uuid.uuid4()), role="secretary")
    resp = await client.post(
        "/api/v1/predict/feedback",
        json={
            "appointment_uuid": str(appt_uuid),
            "actual_status": "COMPLETED",
            "was_predicted_correctly": True,
            "prediction_prob": 0.15,
            "model_version": "v1.0",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
