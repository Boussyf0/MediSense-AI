from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd

from app.api.v1.endpoints.metrics import (
    noshow_predictions_total,
    prediction_latency_seconds,
)

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "age",
    "sex",
    "distance_to_clinic",
    "weather_score",
    "previous_noshows",
    "days_since_booking",
    "day_of_week",
    "appointment_hour",
    "chronic_conditions_count",
]
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
METADATA_PATH = MODELS_DIR / "noshow_training_report.json"
ORANGE_THRESHOLD = 0.20
RED_THRESHOLD = 0.40


class ModelNotReadyError(RuntimeError):
    """Raised when prediction artifacts are unavailable."""


class FeatureValidationError(ValueError):
    """Raised when input features cannot be processed."""


def get_risk_color(probability: float) -> str:
    """Map a no-show probability to traffic-light risk labels."""
    if probability > RED_THRESHOLD:
        return "red"
    if probability >= ORANGE_THRESHOLD:
        return "orange"
    return "green"


def build_appointment_features(
    *,
    patient,  # app.db.models.patient.Patient
    appointment,  # app.db.models.appointment.Appointment
    previous_noshows: int,
    now,  # datetime in UTC
    default_distance_km: float = 5.0,
    default_weather_score: float = 0.5,
) -> Dict[str, Any]:
    """
    Compose the FEATURE_COLUMNS dict for the no-show model from DB state.

    Patient.distance_to_clinic and weather_score aren't stored — sensible
    defaults are used so a prediction can always be made at booking time.
    Once those columns/feeds exist they replace the defaults.
    """
    birth_year = patient.birth_year or (now.year - 35)
    age = max(0, min(120, now.year - birth_year))
    sex = (patient.sex or "M").upper()
    if sex not in ("M", "F"):
        sex = "M"
    chronic_count = len(patient.chronic_conditions or [])
    days_since_booking = max(0, (appointment.scheduled_at - now).days)
    return {
        "age": age,
        "sex": sex,
        "distance_to_clinic": default_distance_km,
        "weather_score": default_weather_score,
        "previous_noshows": previous_noshows,
        "days_since_booking": days_since_booking,
        "day_of_week": appointment.scheduled_at.weekday(),
        "appointment_hour": appointment.scheduled_at.hour,
        "chronic_conditions_count": chronic_count,
    }


class NoShowPredictor:
    """Service handling no-show inference and feature explainability."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NoShowPredictor, cls).__new__(cls)
            cls._instance._load_models()
        return cls._instance

    def _load_models(self) -> None:
        """Load trained model artifacts.

        Loading order for the sklearn model:
          1. MLflow registry alias ``@champion`` — consumed when MLflow tracking
             server is reachable and a champion version has been promoted via
             ``register_noshow_model.py``.
          2. Local joblib file ``backend/models/noshow_model.joblib`` — fallback
             for local development or when MLflow is unavailable.

        The SHAP explainer, scaler, and label encoder are always loaded from
        their joblib files; they are not stored in the MLflow model registry.
        """
        self.model = None
        self.explainer = None
        self.scaler = None
        self.label_encoder = None
        self.model_version = "v5.0-xgb"

        try:
            # ── 1. Try MLflow registry @champion ─────────────────────────────
            model_loaded = False
            try:
                import mlflow.sklearn  # type: ignore[import]  # pragma: no cover
                from app.core.config import get_settings  # pragma: no cover
                _settings = get_settings()  # pragma: no cover
                model_uri = f"models:/{_settings.MLFLOW_MODEL_NAME}@champion"  # pragma: no cover
                self.model = mlflow.sklearn.load_model(model_uri)  # pragma: no cover
                model_loaded = True  # pragma: no cover
                logger.info("noshow_model_loaded_from_registry uri=%s", model_uri)  # pragma: no cover
            except Exception as mlflow_exc:
                logger.debug(
                    "MLflow registry unavailable, falling back to joblib: %s", mlflow_exc
                )

            # ── 2. Fallback: local joblib file ────────────────────────────────
            if not model_loaded:
                model_path = MODELS_DIR / "noshow_model.joblib"
                legacy_model_path = MODELS_DIR / "noshow_xgb_model.joblib"
                selected_model_path = model_path if model_path.exists() else legacy_model_path
                self.model = joblib.load(selected_model_path)
                logger.info("noshow_model_loaded_from_joblib path=%s", selected_model_path)

            # ── 3. Always load auxiliary artifacts from joblib ────────────────
            self.explainer = joblib.load(MODELS_DIR / "noshow_shap_explainer.joblib")
            self.scaler = joblib.load(MODELS_DIR / "noshow_scaler.joblib")
            self.label_encoder = joblib.load(MODELS_DIR / "noshow_label_encoder.joblib")

            if METADATA_PATH.exists():
                with METADATA_PATH.open("r", encoding="utf-8") as fp:
                    metadata = json.load(fp)
                winner = metadata.get("winner_model")
                mlflow_run_id = metadata.get("mlflow_run_id", "")
                if isinstance(winner, str) and winner:
                    if mlflow_run_id:
                        self.model_version = f"v6.0-{winner}-run{mlflow_run_id[:8]}"
                    else:
                        self.model_version = f"v5.1-{winner}"
        except Exception as exc:
            logger.exception("Unable to load no-show model artifacts: %s", exc)

    def _build_shap_contributions(self, transformed_features: np.ndarray) -> Dict[str, float]:
        shap_values = self.explainer.shap_values(transformed_features)

        if isinstance(shap_values, list):
            if not shap_values:
                raise FeatureValidationError("SHAP output is empty")
            shap_vector = np.asarray(shap_values[-1][0], dtype=float)
        else:
            shap_array = np.asarray(shap_values, dtype=float)
            if shap_array.ndim == 3:
                shap_vector = shap_array[0, :, -1]
            elif shap_array.ndim == 2:
                shap_vector = shap_array[0]
            else:
                raise FeatureValidationError("Unexpected SHAP output shape")

        return {column: float(value) for column, value in zip(FEATURE_COLUMNS, shap_vector)}

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict no-show probability and return SHAP contributions."""
        if any(artifact is None for artifact in (self.model, self.explainer, self.scaler, self.label_encoder)):
            raise ModelNotReadyError("No-show model artifacts are not available")

        missing_columns = [col for col in FEATURE_COLUMNS if col not in features]
        if missing_columns:
            raise FeatureValidationError(f"Missing required features: {', '.join(missing_columns)}")

        try:
            with prediction_latency_seconds.labels(model="noshow").time():
                input_df = pd.DataFrame([features], columns=FEATURE_COLUMNS)
                input_df["sex"] = self.label_encoder.transform(input_df["sex"])
                transformed_features = self.scaler.transform(input_df)

                probability = float(self.model.predict_proba(transformed_features)[0, 1])
                shap_contributions = self._build_shap_contributions(transformed_features)

            risk_color = get_risk_color(probability)
            noshow_predictions_total.labels(risk_level=risk_color).inc()
        except ValueError as exc:
            raise FeatureValidationError(str(exc)) from exc

        return {
            "noshow_probability": round(probability, 4),
            "risk_color": risk_color,
            "shap_contributions": shap_contributions,
            "model_version": self.model_version,
        }


noshow_predictor = NoShowPredictor()
