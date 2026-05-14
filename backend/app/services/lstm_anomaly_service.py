"""
LSTM Anomaly Service — Sprint 7 (US-27/28).

Loads the trained BiLSTM model and scores biometric windows.
Returns an anomaly score in [0, 1]; scores above LSTM_ANOMALY_THRESHOLD
are classified as critical anomalies.

The model file is loaded lazily on first call and cached for the process lifetime.
Falls back gracefully if the model file is not yet present (returns score=0.0).
"""
import logging
from pathlib import Path

import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_model = None        # cached nn.Module
_device = None       # cached torch.device


def _build_model_from_checkpoint(checkpoint: dict):  # pragma: no cover
    """
    Reconstruct BiLSTM from a saved checkpoint dict.
    Excluded from coverage: requires torch installed + a real .pt checkpoint file.
    External I/O adapter — only reachable when model file exists on disk.
    """
    import torch
    import torch.nn as nn

    cfg = checkpoint["config"]

    class BahdanauAttention(nn.Module):
        def __init__(self, hidden_dim: int) -> None:
            super().__init__()
            self.W = nn.Linear(hidden_dim * 2, hidden_dim)
            self.v = nn.Linear(hidden_dim, 1, bias=False)

        def forward(self, enc_out: torch.Tensor) -> torch.Tensor:
            energy = torch.tanh(self.W(enc_out))
            scores = self.v(energy).squeeze(-1)
            weights = torch.softmax(scores, dim=-1).unsqueeze(-1)
            return (enc_out * weights).sum(dim=1)

    class BiLSTMAnomalyDetector(nn.Module):
        def __init__(self, n_features, hidden_dim, n_layers, dropout) -> None:
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=n_features, hidden_size=hidden_dim,
                num_layers=n_layers, batch_first=True,
                bidirectional=True,
                dropout=dropout if n_layers > 1 else 0.0,
            )
            self.attention = BahdanauAttention(hidden_dim)
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Sequential(
                nn.Linear(hidden_dim * 2, 64), nn.ReLU(),
                nn.Dropout(dropout), nn.Linear(64, 1), nn.Sigmoid(),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            out, _ = self.lstm(x)
            ctx = self.attention(out)
            return self.fc(self.dropout(ctx)).squeeze(-1)

    model = BiLSTMAnomalyDetector(
        n_features=cfg["n_features"],
        hidden_dim=cfg["hidden_dim"],
        n_layers=cfg["n_layers"],
        dropout=cfg["dropout"],
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    device = torch.device("cpu")
    return model, device


def _load_model():
    global _model, _device
    if _model is not None:
        return _model, _device

    model_path = Path(settings.LSTM_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = Path(__file__).resolve().parents[3] / "backend" / settings.LSTM_MODEL_PATH

    if not model_path.exists():
        logger.warning("LSTM model not found at %s — anomaly scoring disabled", model_path)
        return None, None

    try:
        import torch
        checkpoint = torch.load(str(model_path), map_location="cpu")
        _model, _device = _build_model_from_checkpoint(checkpoint)
        logger.info("LSTM anomaly model loaded from %s", model_path)
        return _model, _device
    except Exception as exc:
        logger.error("Failed to load LSTM model: %s", exc)
        return None, None


def _run_inference(model, device, vitals: list[dict]) -> float:  # pragma: no cover
    """
    Run BiLSTM forward pass on a normalised window tensor.
    Excluded from coverage: only reachable when model is loaded from disk.
    External I/O adapter — depends on torch and a loaded nn.Module.
    """
    import torch

    seq_len = 120
    raw = []
    for v in vitals[-seq_len:]:
        raw.append([
            float(v.get("hr", 70)),
            float(v.get("spo2", 98)),
            float(v.get("hrv", 40)),
            float(v.get("temperature", 36.6)),
        ])
    while len(raw) < seq_len:
        raw.insert(0, raw[0] if raw else [70, 98, 40, 36.6])

    arr = np.array(raw, dtype=np.float32)
    mean = arr.mean(axis=0, keepdims=True)
    std  = arr.std(axis=0, keepdims=True) + 1e-8
    arr  = (arr - mean) / std

    x = torch.tensor(arr).unsqueeze(0).to(device)
    with torch.no_grad():
        return float(model(x).item())


def score_window(vitals: list[dict]) -> float:
    """
    Score a list of biometric readings as an anomaly probability.

    vitals: list of dicts with keys hr, spo2, hrv, temperature (newest last).
    Returns float in [0, 1] — probability of anomaly.
    """
    model, device = _load_model()
    if model is None:
        return 0.0

    try:
        return _run_inference(model, device, vitals)
    except Exception as exc:
        logger.error("LSTM inference error: %s", exc)
        return 0.0


def is_critical(score: float) -> bool:
    return score >= settings.LSTM_ANOMALY_THRESHOLD
