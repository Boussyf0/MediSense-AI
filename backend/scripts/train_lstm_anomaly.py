#!/usr/bin/env python3
"""
BiLSTM Anomaly Detector — Sprint 7 (US-27).

Trains a bidirectional LSTM with Bahdanau attention on synthetic biometric
windows from Samsung Watch sensors (HR, SpO2, HRV, temperature).

Quality gates:
  AUC-ROC > 0.85  (hard gate — exits 1 if not met)
  F1      > 0.78  (hard gate)

Usage:
  python scripts/train_lstm_anomaly.py              # full training (~10 min)
  python scripts/train_lstm_anomaly.py --quick      # 5 epochs, 2k samples (CI/demo)
  python scripts/train_lstm_anomaly.py --epochs 30
"""
import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.pytorch
import numpy as np

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.metrics import (
        classification_report, f1_score, roc_auc_score, roc_curve,
        confusion_matrix,
    )
except ImportError as exc:
    print(f"Missing dependency: {exc}")
    print("pip install torch scikit-learn")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parents[2]
MODEL_DIR  = BASE_DIR / "backend" / "models"
RESULT_DIR = BASE_DIR / "backend" / "results"
MLFLOW_DIR = BASE_DIR / "backend" / ".local" / "mlflow"
MLFLOW_TRACKING_URI = (MLFLOW_DIR / "runs").resolve().as_uri()

EXPERIMENT_NAME = "LSTM-Anomaly-Detection-Sprint7"
MODEL_NAME      = "lstm-anomaly-detector"
RANDOM_STATE    = 42

# ── Hyper-parameters ──────────────────────────────────────────────────────
SEQ_LEN    = 120   # timesteps per window (~2 minutes at 1 Hz)
N_FEATURES = 4     # HR, SpO2, HRV, temperature
HIDDEN_DIM = 128
N_LAYERS   = 2
DROPOUT    = 0.3
BATCH_SIZE = 64
LR         = 1e-3

AUC_THRESHOLD = 0.85
F1_THRESHOLD  = 0.78


# ── Model ─────────────────────────────────────────────────────────────────

class BahdanauAttention(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.W = nn.Linear(hidden_dim * 2, hidden_dim)
        self.v = nn.Linear(hidden_dim, 1, bias=False)

    def forward(self, encoder_output: torch.Tensor) -> torch.Tensor:
        # encoder_output: (batch, seq_len, hidden*2)
        energy = torch.tanh(self.W(encoder_output))       # (batch, seq, hidden)
        scores = self.v(energy).squeeze(-1)                # (batch, seq)
        weights = torch.softmax(scores, dim=-1).unsqueeze(-1)  # (batch, seq, 1)
        context = (encoder_output * weights).sum(dim=1)   # (batch, hidden*2)
        return context


class BiLSTMAnomalyDetector(nn.Module):
    def __init__(
        self,
        n_features: int = N_FEATURES,
        hidden_dim: int = HIDDEN_DIM,
        n_layers: int = N_LAYERS,
        dropout: float = DROPOUT,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.attention = BahdanauAttention(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, n_features)
        out, _ = self.lstm(x)                  # (batch, seq, hidden*2)
        context = self.attention(out)          # (batch, hidden*2)
        context = self.dropout(context)
        return self.fc(context).squeeze(-1)    # (batch,)


# ── Synthetic data generation ─────────────────────────────────────────────

def _patient_baseline() -> dict:
    rng = np.random.default_rng()
    return {
        "hr":   rng.uniform(60, 80),
        "spo2": rng.uniform(96, 99),
        "hrv":  rng.uniform(30, 60),
        "temp": rng.uniform(36.3, 37.0),
    }


def generate_normal_window(rng: np.random.Generator, baseline: dict) -> np.ndarray:
    hr   = baseline["hr"]   + rng.normal(0, 3,  SEQ_LEN)
    spo2 = baseline["spo2"] + rng.normal(0, 0.5, SEQ_LEN)
    hrv  = baseline["hrv"]  + rng.normal(0, 5,  SEQ_LEN)
    temp = baseline["temp"] + rng.normal(0, 0.1, SEQ_LEN)
    window = np.stack([hr, spo2, hrv, temp], axis=-1).astype(np.float32)
    return window


def generate_anomaly_window(rng: np.random.Generator, baseline: dict) -> np.ndarray:
    anomaly_type = rng.choice(["bradycardia", "hypoxia", "combined", "fever"])
    hr   = baseline["hr"]   + rng.normal(0, 3,  SEQ_LEN)
    spo2 = baseline["spo2"] + rng.normal(0, 0.5, SEQ_LEN)
    hrv  = baseline["hrv"]  + rng.normal(0, 5,  SEQ_LEN)
    temp = baseline["temp"] + rng.normal(0, 0.1, SEQ_LEN)

    onset = rng.integers(SEQ_LEN // 3, SEQ_LEN // 2)
    if anomaly_type in ("bradycardia", "combined"):
        hr[onset:]   -= rng.uniform(15, 30)
        hrv[onset:]  -= rng.uniform(10, 20)
    if anomaly_type in ("hypoxia", "combined"):
        spo2[onset:] -= rng.uniform(5, 12)
    if anomaly_type == "fever":
        temp[onset:] += rng.uniform(1.2, 2.5)

    window = np.stack([hr, spo2, hrv, temp], axis=-1).astype(np.float32)
    return window


def normalize_window(window: np.ndarray) -> np.ndarray:
    mean = window.mean(axis=0, keepdims=True)
    std  = window.std(axis=0, keepdims=True) + 1e-8
    return ((window - mean) / std).astype(np.float32)


def generate_dataset(n_normal: int, n_anomaly: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(RANDOM_STATE)
    X, y = [], []

    for _ in range(n_normal):
        baseline = _patient_baseline()
        w = generate_normal_window(rng, baseline)
        X.append(normalize_window(w))
        y.append(0)

    for _ in range(n_anomaly):
        baseline = _patient_baseline()
        w = generate_anomaly_window(rng, baseline)
        X.append(normalize_window(w))
        y.append(1)

    idx = rng.permutation(len(X))
    return np.array(X)[idx], np.array(y, dtype=np.float32)[idx]


# ── Training ──────────────────────────────────────────────────────────────

def make_loaders(
    X: np.ndarray,
    y: np.ndarray,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    n = len(X)
    n_train = int(0.70 * n)
    n_val   = int(0.15 * n)

    X_t = torch.tensor(X[:n_train])
    y_t = torch.tensor(y[:n_train])
    X_v = torch.tensor(X[n_train:n_train + n_val])
    y_v = torch.tensor(y[n_train:n_train + n_val])
    X_te = torch.tensor(X[n_train + n_val:])
    y_te  = torch.tensor(y[n_train + n_val:])

    train_ds = TensorDataset(X_t, y_t)
    val_ds   = TensorDataset(X_v, y_v)
    test_ds  = TensorDataset(X_te, y_te)

    return (
        DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True),
        DataLoader(val_ds,   batch_size=BATCH_SIZE),
        DataLoader(test_ds,  batch_size=BATCH_SIZE),
    )


def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    for X_batch, y_batch in loader:
        X_batch, y_batch = X_batch.to(device), y_batch.to(device)
        optimizer.zero_grad()
        preds = model(X_batch)
        loss = criterion(preds, y_batch)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        total_loss += loss.item() * len(X_batch)
    return total_loss / len(loader.dataset)


def evaluate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, np.ndarray, np.ndarray]:
    model.eval()
    all_probs, all_labels = [], []
    total_loss = 0.0
    with torch.no_grad():
        for X_batch, y_batch in loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            probs = model(X_batch)
            total_loss += criterion(probs, y_batch).item() * len(X_batch)
            all_probs.extend(probs.cpu().numpy())
            all_labels.extend(y_batch.cpu().numpy())
    return (
        total_loss / len(loader.dataset),
        np.array(all_probs),
        np.array(all_labels),
    )


def register_lstm_model(run_id: str) -> None:
    client = mlflow.tracking.MlflowClient()
    try:
        registered = mlflow.register_model(
            f"runs:/{run_id}/model",
            MODEL_NAME,
        )
        client.set_registered_model_alias(MODEL_NAME, "champion", registered.version)
        print(f"Registered version {registered.version} as 'champion'")
    except Exception as exc:
        print(f"MLflow registration skipped: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────

def run_training(epochs: int, n_normal: int, n_anomaly: int) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    MLFLOW_DIR.mkdir(parents=True, exist_ok=True)
    (MLFLOW_DIR / "runs").mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    print(f"Generating dataset: {n_normal} normal + {n_anomaly} anomaly windows...")
    X, y = generate_dataset(n_normal, n_anomaly)
    train_loader, val_loader, test_loader = make_loaders(X, y)
    print(f"Train={len(train_loader.dataset)}  Val={len(val_loader.dataset)}  Test={len(test_loader.dataset)}")

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    with mlflow.start_run() as active_run:
        run_id = active_run.info.run_id
        mlflow.log_params({
            "epochs": epochs,
            "seq_len": SEQ_LEN,
            "n_features": N_FEATURES,
            "hidden_dim": HIDDEN_DIM,
            "n_layers": N_LAYERS,
            "dropout": DROPOUT,
            "batch_size": BATCH_SIZE,
            "lr": LR,
            "n_normal": n_normal,
            "n_anomaly": n_anomaly,
        })

        model = BiLSTMAnomalyDetector().to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", patience=3, factor=0.5
        )

        criterion = nn.BCELoss()

        best_val_auc = 0.0
        best_state = None

        for epoch in range(1, epochs + 1):
            train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
            val_loss, val_probs, val_labels = evaluate(model, val_loader, criterion, device)
            val_auc = roc_auc_score(val_labels, val_probs)
            scheduler.step(val_loss)

            mlflow.log_metrics({
                "train_loss": train_loss,
                "val_loss": val_loss,
                "val_auc": val_auc,
            }, step=epoch)
            print(f"Epoch {epoch:3d}/{epochs}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  val_auc={val_auc:.4f}")

            if val_auc > best_val_auc:
                best_val_auc = val_auc
                best_state = {k: v.clone() for k, v in model.state_dict().items()}

        # Load best checkpoint
        if best_state is not None:
            model.load_state_dict(best_state)

        # Test set evaluation
        _, test_probs, test_labels = evaluate(model, test_loader, criterion, device)
        test_preds = (test_probs >= 0.5).astype(int)
        test_auc = roc_auc_score(test_labels, test_probs)
        test_f1  = f1_score(test_labels, test_preds)

        print(f"\nTest Set:")
        print(classification_report(test_labels, test_preds, target_names=["Normal", "Anomaly"]))
        print(f"AUC-ROC: {test_auc:.4f}  F1: {test_f1:.4f}")

        mlflow.log_metrics({"test_auc": test_auc, "test_f1": test_f1})

        # ROC curve plot
        fpr, tpr, _ = roc_curve(test_labels, test_probs)
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        axes[0].plot(fpr, tpr, label=f"AUC={test_auc:.3f}")
        axes[0].plot([0, 1], [0, 1], "k--")
        axes[0].set_xlabel("False Positive Rate")
        axes[0].set_ylabel("True Positive Rate")
        axes[0].set_title("ROC Curve — BiLSTM Anomaly Detector")
        axes[0].legend()
        axes[0].grid(alpha=0.3)

        cm = confusion_matrix(test_labels, test_preds)
        axes[1].imshow(cm, cmap="Blues")
        axes[1].set_title("Confusion Matrix")
        for i in range(2):
            for j in range(2):
                axes[1].text(j, i, str(cm[i, j]), ha="center", va="center", fontsize=14)
        axes[1].set_xticks([0, 1])
        axes[1].set_yticks([0, 1])
        axes[1].set_xticklabels(["Normal", "Anomaly"])
        axes[1].set_yticklabels(["Normal", "Anomaly"])
        axes[1].set_xlabel("Predicted")
        axes[1].set_ylabel("True")

        plot_path = RESULT_DIR / "lstm_anomaly_roc_confusion.png"
        fig.tight_layout()
        fig.savefig(plot_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        mlflow.log_artifact(str(plot_path), artifact_path="plots")

        # Save model
        model_path = MODEL_DIR / "lstm_anomaly_detector.pt"
        torch.save({"model_state_dict": model.state_dict(), "config": {
            "n_features": N_FEATURES, "hidden_dim": HIDDEN_DIM,
            "n_layers": N_LAYERS, "dropout": DROPOUT, "seq_len": SEQ_LEN,
        }}, model_path)
        mlflow.pytorch.log_model(model, artifact_path="model")

        # Training report
        report = {
            "experiment": EXPERIMENT_NAME,
            "mlflow_run_id": run_id,
            "test_metrics": {"auc": float(test_auc), "f1": float(test_f1)},
            "config": {
                "seq_len": SEQ_LEN, "n_features": N_FEATURES,
                "hidden_dim": HIDDEN_DIM, "n_layers": N_LAYERS,
                "epochs": epochs,
            },
        }
        report_path = MODEL_DIR / "lstm_anomaly_training_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        mlflow.log_artifact(str(report_path), artifact_path="reports")

        # ── Quality gate ───────────────────────────────────────
        f1_thresh  = float(os.getenv("LSTM_F1_THRESHOLD",  str(F1_THRESHOLD)))
        auc_thresh = float(os.getenv("LSTM_AUC_THRESHOLD", str(AUC_THRESHOLD)))

        print(f"\n{'─'*50}")
        print(f"Quality gate:  AUC={test_auc:.4f} (>={auc_thresh})  F1={test_f1:.4f} (>={f1_thresh})")

        if test_auc >= auc_thresh and test_f1 >= f1_thresh:
            register_lstm_model(run_id)
            print(f"GATE PASSED — model saved to {model_path}")
        else:
            print("GATE FAILED — thresholds not met; model NOT registered")
            sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--quick", action="store_true",
                        help="Fast run: 5 epochs, 2 000 samples (CI/demo)")
    args = parser.parse_args()

    if args.quick:
        run_training(epochs=5, n_normal=1500, n_anomaly=500)
    else:
        run_training(epochs=args.epochs, n_normal=5000, n_anomaly=1500)


if __name__ == "__main__":
    main()
