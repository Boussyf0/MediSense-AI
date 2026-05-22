"""
Behavioural tests for the trained BiLSTM anomaly detector.

Skipped automatically when the model artefact is missing — the tests run
in CI after `train_lstm_anomaly.py --quick` has produced
`backend/models/lstm_anomaly_detector.pt`.
"""
from pathlib import Path

import pytest

from app.core.config import get_settings


def _model_path() -> Path:
    p = Path(get_settings().LSTM_MODEL_PATH)
    if not p.is_absolute():
        p = Path(__file__).resolve().parents[1] / p
    return p


pytestmark = pytest.mark.skipif(
    not _model_path().exists(),
    reason="LSTM model not trained — run scripts/train_lstm_anomaly.py --quick",
)


def _calm_vitals(n: int = 120) -> list[dict]:
    return [{"hr": 72, "spo2": 98, "hrv": 42, "temperature": 36.6} for _ in range(n)]


def _anomalous_vitals(n: int = 120) -> list[dict]:
    """Window that ends with a sustained tachycardia + hypoxia drop."""
    onset = n // 2
    series = []
    for i in range(n):
        if i < onset:
            series.append({"hr": 70, "spo2": 98, "hrv": 45, "temperature": 36.6})
        else:
            series.append({"hr": 110, "spo2": 88, "hrv": 18, "temperature": 38.2})
    return series


def _reset_module_cache():
    from app.services import lstm_anomaly_service
    lstm_anomaly_service._model = None
    lstm_anomaly_service._device = None


def test_score_window_calm_is_low():
    _reset_module_cache()
    from app.services.lstm_anomaly_service import score_window

    score = score_window(_calm_vitals())
    assert 0.0 <= score < 0.3, f"calm window scored unexpectedly high: {score}"


def test_score_window_anomalous_is_high():
    _reset_module_cache()
    from app.services.lstm_anomaly_service import score_window

    score = score_window(_anomalous_vitals())
    assert score > 0.7, f"injected anomaly scored unexpectedly low: {score}"


def test_score_window_is_critical_threshold():
    _reset_module_cache()
    from app.services.lstm_anomaly_service import score_window, is_critical

    assert is_critical(score_window(_anomalous_vitals())) is True
    assert is_critical(score_window(_calm_vitals())) is False
