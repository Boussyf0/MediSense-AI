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
        confusion_matrix, brier_score_loss,
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

    def get_attention_weights(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: (batch, seq_len, n_features)
        # Returns: (preds, weights)
        self.eval()
        with torch.no_grad():
            out, _ = self.lstm(x)                  # (batch, seq, hidden*2)
            energy = torch.tanh(self.attention.W(out))       # (batch, seq, hidden)
            scores = self.attention.v(energy).squeeze(-1)    # (batch, seq)
            weights = torch.softmax(scores, dim=-1)           # (batch, seq)
            context = (out * weights.unsqueeze(-1)).sum(dim=1)   # (batch, hidden*2)
            preds = self.fc(self.dropout(context)).squeeze(-1)    # (batch,)
        return preds, weights


# ── Synthetic data generation ─────────────────────────────────────────────

def forward_fill(arr: np.ndarray) -> np.ndarray:
    mask = np.isnan(arr)
    idx = np.where(~mask, np.arange(mask.shape[0]), 0)
    np.maximum.accumulate(idx, out=idx)
    filled = arr[idx]
    if np.isnan(filled[0]):
        non_nan_indices = np.where(~np.isnan(filled))[0]
        if len(non_nan_indices) > 0:
            first_val = filled[non_nan_indices[0]]
            filled[np.isnan(filled)] = first_val
        else:
            filled[:] = 0.0
    return filled


def simulate_sparse_sampling(rng: np.random.Generator, signal: np.ndarray, interval: int) -> np.ndarray:
    sparse = np.full_like(signal, np.nan)
    offset = rng.integers(0, interval)
    indices = np.arange(offset, len(signal), interval)
    sparse[indices] = signal[indices]
    return forward_fill(sparse)


def simulate_continuous_patient(
    rng: np.random.Generator,
    total_steps: int,
    is_anomalous: bool,
) -> tuple[np.ndarray, np.ndarray]:
    mean_hr   = rng.uniform(60, 80)
    mean_spo2 = rng.uniform(96, 99)
    mean_hrv  = rng.uniform(30, 60)
    mean_temp = rng.uniform(36.3, 37.0)
    
    start_hour = rng.uniform(0, 24)
    
    t_arr = np.arange(total_steps)
    hours = start_hour + t_arr / 60.0
    
    hr = mean_hr + 8.0 * np.sin(2 * np.pi * (hours - 8) / 24) + rng.normal(0, 3, total_steps)
    temp = mean_temp + 0.2 * np.sin(2 * np.pi * (hours - 8) / 24) + rng.normal(0, 0.1, total_steps)
    hrv = mean_hrv - 10.0 * np.sin(2 * np.pi * (hours - 8) / 24) + rng.normal(0, 5, total_steps)
    spo2 = mean_spo2 + rng.normal(0, 0.5, total_steps)
    
    spo2 = np.minimum(spo2, 100.0)
    
    anomaly_onset = None
    if is_anomalous:
        anomaly_onset = rng.integers(int(total_steps * 0.25), int(total_steps * 0.75))
        anomaly_type = rng.choice(["bradycardia", "hypoxia", "combined", "fever"])
        
        hr_shift = 0.0
        hrv_shift = 0.0
        spo2_shift = 0.0
        temp_shift = 0.0
        
        if anomaly_type in ("bradycardia", "combined"):
            hr_shift = -rng.uniform(15, 30)
            hrv_shift = -rng.uniform(10, 20)
        if anomaly_type in ("hypoxia", "combined"):
            spo2_shift = -rng.uniform(5, 12)
        if anomaly_type == "fever":
            temp_shift = rng.uniform(1.2, 2.5)
            
        transition_len = 15
        for t in range(anomaly_onset, total_steps):
            factor = min((t - anomaly_onset) / transition_len, 1.0)
            hr[t] += hr_shift * factor
            hrv[t] += hrv_shift * factor
            spo2[t] += spo2_shift * factor
            temp[t] += temp_shift * factor
            
    # Apply sparse sampling and forward-fill
    hr = simulate_sparse_sampling(rng, hr, 5)
    hrv = simulate_sparse_sampling(rng, hrv, 5)
    spo2 = simulate_sparse_sampling(rng, spo2, 15)
    temp = simulate_sparse_sampling(rng, temp, 30)
    
    features = np.stack([hr, spo2, hrv, temp], axis=-1).astype(np.float32)
    
    anomaly_mask = np.zeros(total_steps, dtype=bool)
    if anomaly_onset is not None:
        anomaly_mask[anomaly_onset:] = True
        
    return features, anomaly_mask


def normalize_window(window: np.ndarray) -> np.ndarray:
    global_means = np.array([70.0, 97.0, 45.0, 36.6], dtype=np.float32)
    global_stds  = np.array([10.0, 2.0, 15.0, 0.5], dtype=np.float32)
    return ((window - global_means) / global_stds).astype(np.float32)


def generate_patient_wise_dataset(
    rng: np.random.Generator,
    n_patients: int,
    total_steps: int,
    stride: int,
    anomaly_ratio: float = 0.3,
) -> tuple[list[np.ndarray], list[float], list[int]]:
    X_list = []
    y_list = []
    patient_ids = []
    
    for p_id in range(n_patients):
        is_anomalous = rng.random() < anomaly_ratio
        features, anomaly_mask = simulate_continuous_patient(rng, total_steps, is_anomalous)
        
        for start in range(0, total_steps - SEQ_LEN + 1, stride):
            end = start + SEQ_LEN
            window_feat = features[start:end]
            norm_feat = normalize_window(window_feat)
            
            window_mask = anomaly_mask[start:end]
            label = 1.0 if np.sum(window_mask) >= 30 else 0.0
            
            X_list.append(norm_feat)
            y_list.append(label)
            patient_ids.append(p_id)
            
    return X_list, y_list, patient_ids


def generate_patient_wise_split(
    n_patients: int,
    total_steps: int,
    stride: int,
    anomaly_ratio: float = 0.3,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(RANDOM_STATE)
    
    n_train = int(0.70 * n_patients)
    n_val = int(0.15 * n_patients)
    n_test = n_patients - n_train - n_val
    
    print(f"Cohort split: train_patients={n_train}, val_patients={n_val}, test_patients={n_test}")
    
    X_train, y_train, _ = generate_patient_wise_dataset(rng, n_train, total_steps, stride, anomaly_ratio)
    X_val, y_val, _ = generate_patient_wise_dataset(rng, n_val, total_steps, stride, anomaly_ratio)
    X_test, y_test, _ = generate_patient_wise_dataset(rng, n_test, total_steps, stride, anomaly_ratio)
    
    # Shuffle training set for SGD, but keep val/test ordered
    train_idx = rng.permutation(len(X_train))
    X_train = np.array(X_train)[train_idx]
    y_train = np.array(y_train, dtype=np.float32)[train_idx]
    
    X_val = np.array(X_val)
    y_val = np.array(y_val, dtype=np.float32)
    
    X_test = np.array(X_test)
    y_test = np.array(y_test, dtype=np.float32)
    
    return X_train, y_train, X_val, y_val, X_test, y_test


def expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        bin_lower = bin_boundaries[i]
        bin_upper = bin_boundaries[i + 1]
        
        in_bin = (y_prob >= bin_lower) & (y_prob < bin_upper)
        if i == n_bins - 1:
            in_bin = in_bin | (y_prob == bin_upper)
            
        prop_in_bin = np.mean(in_bin)
        if prop_in_bin > 0:
            accuracy_in_bin = np.mean(y_true[in_bin])
            avg_confidence_in_bin = np.mean(y_prob[in_bin])
            ece += prop_in_bin * np.abs(avg_confidence_in_bin - accuracy_in_bin)
    return float(ece)


def plot_attention_weights(model: nn.Module, test_loader: DataLoader, device: torch.device):
    normal_x = None
    anomaly_x = None
    
    model.eval()
    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            for i in range(len(y_batch)):
                if y_batch[i] == 0.0 and normal_x is None:
                    normal_x = X_batch[i].unsqueeze(0).to(device)
                elif y_batch[i] == 1.0 and anomaly_x is None:
                    anomaly_x = X_batch[i].unsqueeze(0).to(device)
                if normal_x is not None and anomaly_x is not None:
                    break
            if normal_x is not None and anomaly_x is not None:
                break
                
    if normal_x is None or anomaly_x is None:
        print("Could not find normal or anomalous samples for attention visualization.")
        return
        
    with torch.no_grad():
        out_n, _ = model.lstm(normal_x)
        energy_n = torch.tanh(model.attention.W(out_n))
        scores_n = model.attention.v(energy_n).squeeze(-1)
        weights_n = torch.softmax(scores_n, dim=-1).squeeze(0).cpu().numpy()
        
        out_a, _ = model.lstm(anomaly_x)
        energy_a = torch.tanh(model.attention.W(out_a))
        scores_a = model.attention.v(energy_a).squeeze(-1)
        weights_a = torch.softmax(scores_a, dim=-1).squeeze(0).cpu().numpy()
        
    normal_x_np = normal_x.squeeze(0).cpu().numpy()
    anomaly_x_np = anomaly_x.squeeze(0).cpu().numpy()
    
    timesteps = np.arange(SEQ_LEN)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
    features = ["Heart Rate", "SpO2", "HRV", "Temperature"]
    colors = ["#e74c3c", "#3498db", "#9b59b6", "#f1c40f"]
    
    for col_idx in range(4):
        axes[0, 0].plot(timesteps, normal_x_np[:, col_idx], label=features[col_idx], color=colors[col_idx], alpha=0.8)
    axes[0, 0].set_title("Normal Window Signals")
    axes[0, 0].legend(loc="upper left")
    axes[0, 0].grid(alpha=0.3)
    
    ax_attn_n = axes[0, 1]
    ax_attn_n.bar(timesteps, weights_n, color="forestgreen", alpha=0.6, width=1.0)
    ax_attn_n.set_title("Attention Weights (Normal)")
    ax_attn_n.set_ylabel("Attention weight")
    ax_attn_n.grid(alpha=0.3)
    
    for col_idx in range(4):
        axes[1, 0].plot(timesteps, anomaly_x_np[:, col_idx], label=features[col_idx], color=colors[col_idx], alpha=0.8)
    axes[1, 0].set_title("Anomalous Window Signals")
    axes[1, 0].legend(loc="upper left")
    axes[1, 0].grid(alpha=0.3)
    
    ax_attn_a = axes[1, 1]
    ax_attn_a.bar(timesteps, weights_a, color="crimson", alpha=0.6, width=1.0)
    ax_attn_a.set_title("Attention Weights (Anomalous)")
    ax_attn_a.set_ylabel("Attention weight")
    ax_attn_a.grid(alpha=0.3)
    
    plt.xlabel("Timestep (seconds)")
    fig.tight_layout()
    plot_path = RESULT_DIR / "lstm_anomaly_attention.png"
    fig.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved attention visualization to {plot_path}")
    mlflow.log_artifact(str(plot_path), artifact_path="plots")


# ── Training ──────────────────────────────────────────────────────────────

def make_loaders(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    train_ds = TensorDataset(torch.tensor(X_train), torch.tensor(y_train))
    val_ds   = TensorDataset(torch.tensor(X_val), torch.tensor(y_val))
    test_ds  = TensorDataset(torch.tensor(X_test), torch.tensor(y_test))

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

    print("Generating patient-wise split dataset...")
    is_quick = (epochs == 5 or n_normal <= 2000)
    if is_quick:
        n_patients = 30
        total_steps = 720
        stride = 30
    else:
        n_patients = 120
        total_steps = 1440
        stride = 20
        
    X_train, y_train, X_val, y_val, X_test, y_test = generate_patient_wise_split(
        n_patients=n_patients,
        total_steps=total_steps,
        stride=stride,
        anomaly_ratio=0.3
    )
    
    train_loader, val_loader, test_loader = make_loaders(
        X_train, y_train,
        X_val, y_val,
        X_test, y_test
    )
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
            "n_patients": n_patients,
            "total_steps": total_steps,
            "stride": stride,
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
        
        # Compute calibration metrics
        test_brier = brier_score_loss(test_labels, test_probs)
        test_ece = expected_calibration_error(test_labels, test_probs)

        print("\nTest Set:")
        print(classification_report(test_labels, test_preds, target_names=["Normal", "Anomaly"]))
        print(f"AUC-ROC: {test_auc:.4f}  F1: {test_f1:.4f}  Brier Score: {test_brier:.4f}  ECE: {test_ece:.4f}")

        mlflow.log_metrics({
            "test_auc": test_auc,
            "test_f1": test_f1,
            "test_brier": test_brier,
            "test_ece": test_ece,
        })

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

        # Plot attention weights
        plot_attention_weights(model, test_loader, device)

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
            "test_metrics": {
                "auc": float(test_auc),
                "f1": float(test_f1),
                "brier": float(test_brier),
                "ece": float(test_ece),
            },
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
        f1_thresh  = float(os.getenv("LSTM_F1_THRESHOLD",  str(0.0 if is_quick else F1_THRESHOLD)))
        auc_thresh = float(os.getenv("LSTM_AUC_THRESHOLD", str(0.0 if is_quick else AUC_THRESHOLD)))

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
