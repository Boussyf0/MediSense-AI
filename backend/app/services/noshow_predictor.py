from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd

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


class NoShowPredictor:
    """Service handling no-show inference and feature explainability."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NoShowPredictor, cls).__new__(cls)
            cls._instance._load_models()
        return cls._instance

    def _load_models(self) -> None:
        """Load trained model artifacts from backend/models."""
        self.model = None
        self.explainer = None
        self.scaler = None
        self.label_encoder = None
        self.model_version = "v5.0-xgb"

        try:
            self.model = joblib.load(MODELS_DIR / "noshow_xgb_model.joblib")
            self.explainer = joblib.load(MODELS_DIR / "noshow_shap_explainer.joblib")
            self.scaler = joblib.load(MODELS_DIR / "noshow_scaler.joblib")
            self.label_encoder = joblib.load(MODELS_DIR / "noshow_label_encoder.joblib")
            if METADATA_PATH.exists():
                with METADATA_PATH.open("r", encoding="utf-8") as fp:
                    metadata = json.load(fp)
                winner = metadata.get("winner_model")
                if isinstance(winner, str) and winner:
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
            input_df = pd.DataFrame([features], columns=FEATURE_COLUMNS)
            input_df["sex"] = self.label_encoder.transform(input_df["sex"])
            transformed_features = self.scaler.transform(input_df)

            probability = float(self.model.predict_proba(transformed_features)[0, 1])
            shap_contributions = self._build_shap_contributions(transformed_features)
        except ValueError as exc:
            raise FeatureValidationError(str(exc)) from exc

        return {
            "noshow_probability": round(probability, 4),
            "risk_color": get_risk_color(probability),
            "shap_contributions": shap_contributions,
            "model_version": self.model_version,
        }


noshow_predictor = NoShowPredictor()
