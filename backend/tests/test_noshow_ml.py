import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import numpy as np
import pytest

from app.core.security import create_access_token
from app.db.models.appointment import Appointment
from app.db.models.patient import Patient
from app.db.models.user import User, UserRole
from app.services.noshow_predictor import (
    FEATURE_COLUMNS,
    FeatureValidationError,
    ModelNotReadyError,
    build_appointment_features,
    get_risk_color,
    noshow_predictor,
)


def auth(role: str, subject: uuid.UUID | None = None) -> dict[str, str]:
    token = create_access_token(subject=str(subject or uuid.uuid4()), role=role)
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


async def seed_user(test_db, role: UserRole) -> uuid.UUID:
    user_uuid = uuid.uuid4()
    test_db.add(User(
        user_uuid=user_uuid,
        email=f"{role.value}-{user_uuid}@medisense.ai",
        hashed_password="hashed",
        role=role,
        first_name="Test",
        last_name="User",
        is_active=True,
    ))
    await test_db.flush()
    return user_uuid


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


def test_shap_contributions_raise_on_empty_list():
    class FakeExplainer:
        def shap_values(self, _):
            return []

    old_explainer = noshow_predictor.explainer
    try:
        noshow_predictor.explainer = FakeExplainer()
        with pytest.raises(FeatureValidationError, match="SHAP output is empty"):
            noshow_predictor._build_shap_contributions(
                np.zeros((1, len(FEATURE_COLUMNS)))
            )
    finally:
        noshow_predictor.explainer = old_explainer


def test_shap_contributions_handle_3d_array():
    class FakeExplainer:
        def shap_values(self, _):
            return np.zeros((1, len(FEATURE_COLUMNS), 2))

    old_explainer = noshow_predictor.explainer
    try:
        noshow_predictor.explainer = FakeExplainer()
        result = noshow_predictor._build_shap_contributions(
            np.zeros((1, len(FEATURE_COLUMNS)))
        )
        assert set(result.keys()) == set(FEATURE_COLUMNS)
    finally:
        noshow_predictor.explainer = old_explainer


def test_shap_contributions_handle_list_output():
    class FakeExplainer:
        def shap_values(self, _):
            return [np.zeros((1, len(FEATURE_COLUMNS)))]

    old_explainer = noshow_predictor.explainer
    try:
        noshow_predictor.explainer = FakeExplainer()
        result = noshow_predictor._build_shap_contributions(
            np.zeros((1, len(FEATURE_COLUMNS)))
        )
        assert set(result.keys()) == set(FEATURE_COLUMNS)
    finally:
        noshow_predictor.explainer = old_explainer


def test_shap_contributions_raise_on_unexpected_shape():
    class FakeExplainer:
        def shap_values(self, _):
            return np.zeros((len(FEATURE_COLUMNS),))

    old_explainer = noshow_predictor.explainer
    try:
        noshow_predictor.explainer = FakeExplainer()
        with pytest.raises(FeatureValidationError, match="Unexpected SHAP output shape"):
            noshow_predictor._build_shap_contributions(
                np.zeros((1, len(FEATURE_COLUMNS)))
            )
    finally:
        noshow_predictor.explainer = old_explainer


def test_predict_wraps_value_error():
    class FakeModel:
        def predict_proba(self, _):
            return np.array([[0.4, 0.6]])

    class FakeScaler:
        def transform(self, _):
            return np.zeros((1, len(FEATURE_COLUMNS)))

    class FailingEncoder:
        def transform(self, _):
            raise ValueError("bad label")

    class FakeExplainer:
        def shap_values(self, _):
            return np.zeros((1, len(FEATURE_COLUMNS)))

    old_state = (
        noshow_predictor.model,
        noshow_predictor.explainer,
        noshow_predictor.scaler,
        noshow_predictor.label_encoder,
    )
    try:
        noshow_predictor.model = FakeModel()
        noshow_predictor.scaler = FakeScaler()
        noshow_predictor.label_encoder = FailingEncoder()
        noshow_predictor.explainer = FakeExplainer()
        features = {column: 1 for column in FEATURE_COLUMNS}
        features["sex"] = "M"
        with pytest.raises(FeatureValidationError, match="bad label"):
            noshow_predictor.predict(features)
    finally:
        (
            noshow_predictor.model,
            noshow_predictor.explainer,
            noshow_predictor.scaler,
            noshow_predictor.label_encoder,
        ) = old_state


def test_build_appointment_features_normalizes_sex():
    patient_uuid = uuid.uuid4()
    patient = Patient(
        patient_uuid=patient_uuid,
        consent_iot=False,
        consent_nlp=False,
        consent_sharing=False,
        sms_opt_out=False,
        birth_year=1990,
        sex="X",
        city_code="40000",
        chronic_conditions=[],
    )
    appointment = Appointment(
        appointment_uuid=uuid.uuid4(),
        patient_uuid=patient_uuid,
        doctor_uuid=uuid.uuid4(),
        scheduled_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
    )

    features = build_appointment_features(
        patient=patient,
        appointment=appointment,
        previous_noshows=0,
        now=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
    )
    assert features["sex"] == "M"


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
async def test_agenda_batch_patient_forbidden(client):
    response = await client.get(
        f"/api/v1/predictions/no-show/batch?doctor_uuid={uuid.uuid4()}",
        headers=auth("patient"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_agenda_batch_doctor_allowed(client):
    response = await client.get(
        f"/api/v1/predictions/no-show/batch?doctor_uuid={uuid.uuid4()}",
        headers=auth("doctor"),
    )
    assert response.status_code == 200


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

    with patch(
        "app.api.v1.endpoints.agenda.dispatch_smart_sms_reminders",
        new=AsyncMock(return_value=[]),
    ) as mock_dispatch:
        response = await client.get(
            f"/api/v1/predictions/no-show/batch?doctor_uuid={doctor_uuid}&date=2026-06-01",
            headers=auth("secretary"),
        )

    mock_dispatch.assert_not_awaited()
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["risk_color"] == "red"
    assert data[0]["sms_reminders_sent"] == 0


@pytest.mark.asyncio
async def test_agenda_batch_auto_sms_requires_explicit_flag(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment = Appointment(
        appointment_uuid=uuid.uuid4(),
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=0.45,
        sms_reminders_sent=0,
    )
    test_db.add(appointment)
    await test_db.flush()

    with patch(
        "app.api.v1.endpoints.agenda.dispatch_smart_sms_reminders",
        new=AsyncMock(return_value=[]),
    ) as mock_dispatch:
        response = await client.get(
            (
                f"/api/v1/predictions/no-show/batch?doctor_uuid={doctor_uuid}"
                "&date=2026-06-01&auto_send_smart_sms=true"
            ),
            headers=auth("secretary"),
        )

    assert response.status_code == 200
    mock_dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_agenda_batch_returns_null_risk_when_not_scored(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment = Appointment(
        appointment_uuid=uuid.uuid4(),
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=None,
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
    assert data[0]["noshow_probability"] is None
    assert data[0]["risk_color"] is None


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


# ── Unit tests: dispatch_smart_sms_reminders skip paths ──────────────────────

def _make_appt(probability: float, reminders_sent: int = 0) -> MagicMock:
    appt = MagicMock(spec=Appointment)
    appt.noshow_probability = probability
    appt.sms_reminders_sent = reminders_sent
    appt.appointment_uuid = uuid.uuid4()
    appt.patient_uuid = uuid.uuid4()
    appt.scheduled_at = datetime(2027, 6, 1, 9, 0, tzinfo=timezone.utc)
    return appt


def _make_patient(sms_opt_out: bool = False, is_active: bool = True) -> MagicMock:
    p = MagicMock(spec=Patient)
    p.sms_opt_out = sms_opt_out
    p.is_active = is_active
    return p


@pytest.mark.asyncio
async def test_sms_dispatch_below_threshold_skips():
    """Appointment with low risk probability → reason='below_threshold', not sent."""
    from app.services.sms_reminder import dispatch_smart_sms_reminders
    from app.core.config import get_settings

    threshold = get_settings().SMS_REMINDER_THRESHOLD
    appt = _make_appt(probability=threshold - 0.01)
    mock_db = AsyncMock()

    results = await dispatch_smart_sms_reminders(mock_db, [appt])

    assert len(results) == 1
    assert results[0].sent is False
    assert results[0].reason == "below_threshold"
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_sms_dispatch_inactive_patient_skips():
    """Patient not found in DB → reason='patient_inactive_or_missing', not sent."""
    from app.services.sms_reminder import dispatch_smart_sms_reminders

    appt = _make_appt(probability=0.85)
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = None  # patient absent

    mock_db = AsyncMock()
    mock_db.execute.return_value = patient_result

    results = await dispatch_smart_sms_reminders(mock_db, [appt])

    assert results[0].sent is False
    assert results[0].reason == "patient_inactive_or_missing"


@pytest.mark.asyncio
async def test_sms_dispatch_missing_phone_skips():
    """Patient exists but has no phone → reason='missing_phone', not sent."""
    from app.services.sms_reminder import dispatch_smart_sms_reminders

    appt = _make_appt(probability=0.85)
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = _make_patient()

    mock_db = AsyncMock()
    mock_db.execute.return_value = patient_result

    with patch("app.services.sms_reminder._get_patient_phone_number",
               AsyncMock(return_value=None)):
        results = await dispatch_smart_sms_reminders(mock_db, [appt])

    assert results[0].sent is False
    assert results[0].reason == "missing_phone"


@pytest.mark.asyncio
async def test_sms_dispatch_reserve_slot_race_returns_max_reached():
    """_reserve_sms_slot returns None (concurrent update) → reason='max_reminders_reached'."""
    from app.services.sms_reminder import dispatch_smart_sms_reminders

    appt = _make_appt(probability=0.85)
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = _make_patient()

    reserve_result = MagicMock()
    reserve_result.scalar_one_or_none.return_value = None  # concurrent update lost

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [patient_result, reserve_result]

    with patch("app.services.sms_reminder._get_patient_phone_number",
               AsyncMock(return_value="+212600000001")):
        results = await dispatch_smart_sms_reminders(mock_db, [appt])

    assert results[0].sent is False
    assert results[0].reason == "max_reminders_reached"


@pytest.mark.asyncio
async def test_sms_dispatch_send_failure_releases_slot():
    """SMS provider raises → slot released, reason='send_failed'."""
    from app.services.sms_reminder import dispatch_smart_sms_reminders

    appt = _make_appt(probability=0.85)
    patient_result = MagicMock()
    patient_result.scalar_one_or_none.return_value = _make_patient()

    reserve_result = MagicMock()
    reserve_result.scalar_one_or_none.return_value = 1  # slot reserved

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [patient_result, reserve_result, MagicMock()]

    with patch("app.services.sms_reminder._get_patient_phone_number",
               AsyncMock(return_value="+212600000001")), \
         patch("app.services.sms_reminder._send_sms",
               AsyncMock(side_effect=httpx.ConnectError("timeout"))):
        results = await dispatch_smart_sms_reminders(mock_db, [appt])

    assert results[0].sent is False
    assert results[0].reason == "send_failed"


def test_mask_phone_short_number():
    """Phone with ≤2 digits → fully masked; >2 digits shows last two."""
    from app.services.sms_reminder import _mask_phone

    assert _mask_phone("1") == "***"      # 1 digit ≤ 2 → all masked
    assert _mask_phone("12") == "***"     # 2 digits ≤ 2 → all masked
    assert _mask_phone("+212600") == "***00"  # 9 digits → last 2


@pytest.mark.asyncio
async def test_predict_endpoint_success_200(client):
    """Happy path: mocked predictor returns result → 200 with NoShowResponse."""
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
    mock_result = {
        "noshow_probability": 0.35,
        "risk_color": "orange",
        "shap_contributions": {k: 0.01 for k in payload},
        "model_version": "v-test",
    }
    with patch(
        "app.api.v1.endpoints.predict.noshow_predictor.predict",
        return_value=mock_result,
    ):
        response = await client.post(
            "/api/v1/predict/noshow",
            json=payload,
            headers=auth("doctor"),
        )
    assert response.status_code == 200
    data = response.json()
    assert data["noshow_probability"] == pytest.approx(0.35)
    assert data["risk_color"] == "orange"


# ── D2: POST /predictions/no-show/{appointment_uuid}/feedback ─────────────────

@pytest.mark.asyncio
async def test_noshow_feedback_happy(client, test_db):
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment_uuid = uuid.uuid4()
    test_db.add(Appointment(
        appointment_uuid=appointment_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
    ))
    await test_db.flush()

    token = create_access_token(subject=str(doctor_uuid), role="doctor")
    response = await client.post(
        f"/api/v1/predictions/no-show/{appointment_uuid}/feedback",
        json={"outcome": "presented"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["appointment_uuid"] == str(appointment_uuid)
    assert data["outcome"] == "presented"
    assert "id" in data
    assert "created_at" in data
    assert data["updated_predictions"] == 0

    # Verify status was updated to COMPLETED
    await test_db.refresh(
        await test_db.get(Appointment, appointment_uuid)
    )
    appt = await test_db.get(Appointment, appointment_uuid)
    assert appt.status == "COMPLETED"


@pytest.mark.asyncio
async def test_noshow_feedback_no_show_updates_status(client, test_db):
    """Feedback 'no_show' sets appointment status to NO_SHOW."""
    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)
    appointment_uuid = uuid.uuid4()
    test_db.add(Appointment(
        appointment_uuid=appointment_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
    ))
    await test_db.flush()

    secretary_uuid = await seed_user(test_db, UserRole.SECRETARY)
    response = await client.post(
        f"/api/v1/predictions/no-show/{appointment_uuid}/feedback",
        json={"outcome": "no_show"},
        headers=auth("secretary", secretary_uuid),
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "no_show"

    appt = await test_db.get(Appointment, appointment_uuid)
    assert appt.status == "NO_SHOW"


@pytest.mark.asyncio
async def test_noshow_feedback_repredicts_future_appointments(client, test_db):
    """ML loop: marking no_show recalculates future appointment predictions."""
    from datetime import timedelta

    patient_uuid, doctor_uuid = await seed_patient_and_doctor(test_db)

    # Past appointment (the one being evaluated)
    past_uuid = uuid.uuid4()
    test_db.add(Appointment(
        appointment_uuid=past_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=0.30,
    ))

    # Future appointment (should get re-predicted)
    future_uuid = uuid.uuid4()
    test_db.add(Appointment(
        appointment_uuid=future_uuid,
        patient_uuid=patient_uuid,
        doctor_uuid=doctor_uuid,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=7),
        duration_minutes=20,
        status="PENDING",
        noshow_probability=0.20,
    ))
    await test_db.flush()

    mock_prediction = {
        "noshow_probability": 0.55,
        "risk_color": "red",
        "shap_contributions": {},
        "model_version": "v-test-loop",
    }
    secretary_uuid = await seed_user(test_db, UserRole.SECRETARY)
    with patch(
        "app.api.v1.endpoints.agenda.NoShowPredictor"
    ) as MockPredictor:
        mock_instance = MagicMock()
        mock_instance.predict.return_value = mock_prediction
        MockPredictor.return_value = mock_instance

        response = await client.post(
            f"/api/v1/predictions/no-show/{past_uuid}/feedback",
            json={"outcome": "no_show"},
            headers=auth("secretary", secretary_uuid),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["updated_predictions"] == 1

    # Verify future appointment probability was updated
    future_appt = await test_db.get(Appointment, future_uuid)
    assert future_appt.noshow_probability == pytest.approx(0.55)
    assert future_appt.noshow_model_ver == "v-test-loop"


@pytest.mark.asyncio
async def test_noshow_feedback_no_auth_403(client):
    response = await client.post(
        f"/api/v1/predictions/no-show/{uuid.uuid4()}/feedback",
        json={"outcome": "no_show"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_noshow_feedback_unknown_appointment_404(client):
    response = await client.post(
        f"/api/v1/predictions/no-show/{uuid.uuid4()}/feedback",
        json={"outcome": "presented"},
        headers=auth("secretary"),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_noshow_feedback_invalid_outcome_422(client):
    response = await client.post(
        f"/api/v1/predictions/no-show/{uuid.uuid4()}/feedback",
        json={"outcome": "absent"},
        headers=auth("doctor"),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_predict_endpoint_feature_validation_error_422(client):
    """FeatureValidationError from predictor → 422 Unprocessable Entity."""
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
        side_effect=FeatureValidationError("champ manquant"),
    ):
        response = await client.post(
            "/api/v1/predict/noshow",
            json=payload,
            headers=auth("secretary"),
        )
    assert response.status_code == 422
    assert "champ manquant" in response.json()["detail"]
