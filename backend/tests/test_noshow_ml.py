import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole
from app.services.noshow_predictor import (
    FeatureValidationError,
    ModelNotReadyError,
    get_risk_color,
    noshow_predictor,
)


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
        birth_year=1990,
        sex="M",
        city_code="40000",
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


def test_get_risk_color_thresholds():
    assert get_risk_color(0.10) == "green"
    assert get_risk_color(0.20) == "orange"
    assert get_risk_color(0.21) == "orange"
    assert get_risk_color(0.41) == "red"


def test_predict_structure_with_mocked_artifacts():
    class FakeLabelEncoder:
        def transform(self, values):
            return np.array([1 if v == "M" else 0 for v in values])

    class FakeScaler:
        def transform(self, values):
            return values.to_numpy(dtype=float)

    class FakeModel:
        def predict_proba(self, _):
            return np.array([[0.35, 0.65]])

    class FakeExplainer:
        def shap_values(self, X):
            return np.array([[0.1] * X.shape[1]])

    old_state = (
        noshow_predictor.model,
        noshow_predictor.explainer,
        noshow_predictor.scaler,
        noshow_predictor.label_encoder,
        noshow_predictor.model_version,
    )
    try:
        noshow_predictor.model = FakeModel()
        noshow_predictor.explainer = FakeExplainer()
        noshow_predictor.scaler = FakeScaler()
        noshow_predictor.label_encoder = FakeLabelEncoder()
        noshow_predictor.model_version = "v-test"

        features = {
            "age": 45,
            "sex": "M",
            "distance_to_clinic": 10.5,
            "weather_score": 0.2,
            "previous_noshows": 0,
            "days_since_booking": 5,
            "day_of_week": 2,
            "appointment_hour": 14,
            "chronic_conditions_count": 1,
        }
        result = noshow_predictor.predict(features)

        assert set(result.keys()) == {"noshow_probability", "risk_color", "shap_contributions", "model_version"}
        assert result["risk_color"] == "red"
        assert result["model_version"] == "v-test"
        assert set(result["shap_contributions"].keys()) == set(features.keys())
    finally:
        (
            noshow_predictor.model,
            noshow_predictor.explainer,
            noshow_predictor.scaler,
            noshow_predictor.label_encoder,
            noshow_predictor.model_version,
        ) = old_state


def test_predict_missing_features_raises_validation_error():
    old_state = (
        noshow_predictor.model,
        noshow_predictor.explainer,
        noshow_predictor.scaler,
        noshow_predictor.label_encoder,
    )
    try:
        noshow_predictor.model = object()
        noshow_predictor.explainer = object()
        noshow_predictor.scaler = object()
        noshow_predictor.label_encoder = object()

        with pytest.raises(FeatureValidationError):
            noshow_predictor.predict({"age": 30})
    finally:
        (
            noshow_predictor.model,
            noshow_predictor.explainer,
            noshow_predictor.scaler,
            noshow_predictor.label_encoder,
        ) = old_state


@pytest.mark.asyncio
async def test_predict_endpoint_maps_model_not_ready_to_503(client):
    payload = {
        "age": 45,
        "sex": "M",
        "distance_to_clinic": 10.5,
        "weather_score": 0.2,
        "previous_noshows": 0,
        "days_since_booking": 5,
        "day_of_week": 2,
        "appointment_hour": 14,
        "chronic_conditions_count": 1,
    }
    with patch(
        "app.api.v1.endpoints.predict.noshow_predictor.predict",
        side_effect=ModelNotReadyError("artifacts missing"),
    ):
        response = await client.post(
            "/api/v1/predict/noshow",
            json=payload,
            headers=auth("doctor"),
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "artifacts missing"


@pytest.mark.asyncio
async def test_predict_endpoint_patient_forbidden(client):
    payload = {
        "age": 45,
        "sex": "M",
        "distance_to_clinic": 10.5,
        "weather_score": 0.2,
        "previous_noshows": 0,
        "days_since_booking": 5,
        "day_of_week": 2,
        "appointment_hour": 14,
        "chronic_conditions_count": 1,
    }
    response = await client.post(
        "/api/v1/predict/noshow",
        json=payload,
        headers=auth("patient"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_agenda_batch_requires_secretary_or_admin(client):
    response = await client.get(
        f"/api/v1/predictions/no-show/batch?doctor_uuid={uuid.uuid4()}",
        headers=auth("doctor"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_agenda_batch_invalid_date_returns_422(client):
    response = await client.get(
        f"/api/v1/predictions/no-show/batch?doctor_uuid={uuid.uuid4()}&date=2026-13-99",
        headers=auth("secretary"),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_agenda_batch_returns_color_coding(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment = Appointment(
        appointment_uuid=uuid.uuid4(),
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=0.45,
    )
    test_db.add(appointment)
    await test_db.flush()

    response = await client.get(
        f"/api/v1/predictions/no-show/batch?doctor_uuid={doctor_uuid}&date=2026-06-01",
        headers=auth("secretary"),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["risk_color"] == "red"
    assert data[0]["sms_reminders_sent"] == 0


@pytest.mark.asyncio
async def test_feedback_requires_secretary_or_admin(client):
    body = {
        "appointment_uuid": str(uuid.uuid4()),
        "actual_status": "COMPLETED",
        "was_predicted_correctly": True,
        "prediction_prob": 0.12,
        "model_version": "v5.1-xgboost",
    }
    response = await client.post(
        "/api/v1/predict/feedback",
        json=body,
        headers=auth("doctor"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_feedback_not_found_when_appointment_missing(client):
    body = {
        "appointment_uuid": str(uuid.uuid4()),
        "actual_status": "NO_SHOW",
        "was_predicted_correctly": False,
        "prediction_prob": 0.80,
        "model_version": "v5.1-xgboost",
    }
    response = await client.post(
        "/api/v1/predict/feedback",
        json=body,
        headers=auth("secretary"),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_feedback_duplicate_returns_409(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment_uuid = uuid.uuid4()
    appointment = Appointment(
        appointment_uuid=appointment_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="COMPLETED",
        noshow_probability=0.15,
    )
    test_db.add(appointment)
    await test_db.flush()

    body = {
        "appointment_uuid": str(appointment_uuid),
        "actual_status": "COMPLETED",
        "was_predicted_correctly": True,
        "prediction_prob": 0.15,
        "model_version": "v5.1-xgboost",
    }
    first = await client.post(
        "/api/v1/predict/feedback",
        json=body,
        headers=auth("secretary"),
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/predict/feedback",
        json=body,
        headers=auth("secretary"),
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_sms_dispatch_sends_when_probability_above_threshold(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment = Appointment(
        appointment_uuid=uuid.uuid4(),
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=0.65,
        sms_reminders_sent=0,
    )
    test_db.add(appointment)
    await test_db.flush()

    with patch(
        "app.services.sms_reminder._get_patient_phone_number",
        new=AsyncMock(return_value="+212600000001"),
    ), patch(
        "app.services.sms_reminder._send_sms",
        new=AsyncMock(return_value="mock-message-id"),
    ):
        response = await client.post(
            f"/api/v1/predictions/no-show/reminders/dispatch?doctor_uuid={doctor_uuid}&date=2026-06-01",
            headers=auth("secretary"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] == 1
    assert payload["items"][0]["sent"] is True
    assert payload["items"][0]["reason"] == "sent"
    assert payload["items"][0]["sms_reminders_sent"] == 1


@pytest.mark.asyncio
async def test_sms_dispatch_respects_patient_opt_out(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    patient = await test_db.get(Patient, patient_uuid)
    patient.sms_opt_out = True
    appointment = Appointment(
        appointment_uuid=uuid.uuid4(),
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=0.62,
        sms_reminders_sent=0,
    )
    test_db.add(appointment)
    await test_db.flush()

    with patch(
        "app.services.sms_reminder._get_patient_phone_number",
        new=AsyncMock(return_value="+212600000001"),
    ), patch(
        "app.services.sms_reminder._send_sms",
        new=AsyncMock(return_value="mock-message-id"),
    ) as mock_send_sms:
        response = await client.post(
            f"/api/v1/predictions/no-show/reminders/dispatch?doctor_uuid={doctor_uuid}&date=2026-06-01",
            headers=auth("secretary"),
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sent"] == 0
    assert payload["items"][0]["sent"] is False
    assert payload["items"][0]["reason"] == "opt_out"
    mock_send_sms.assert_not_awaited()


@pytest.mark.asyncio
async def test_sms_dispatch_never_exceeds_two_reminders(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment_uuid = uuid.uuid4()
    appointment = Appointment(
        appointment_uuid=appointment_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=0.70,
        sms_reminders_sent=0,
    )
    test_db.add(appointment)
    await test_db.flush()

    with patch(
        "app.services.sms_reminder._get_patient_phone_number",
        new=AsyncMock(return_value="+212600000001"),
    ), patch(
        "app.services.sms_reminder._send_sms",
        new=AsyncMock(return_value="mock-message-id"),
    ) as mock_send_sms:
        for _ in range(3):
            response = await client.post(
                f"/api/v1/predictions/no-show/reminders/dispatch?doctor_uuid={doctor_uuid}&date=2026-06-01",
                headers=auth("secretary"),
            )
            assert response.status_code == 200

    final_payload = response.json()
    assert final_payload["items"][0]["reason"] == "max_reminders_reached"
    assert final_payload["items"][0]["sms_reminders_sent"] == 2
    assert mock_send_sms.await_count == 2
