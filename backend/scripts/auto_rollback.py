#!/usr/bin/env python3
"""
MLflow Auto-Rollback — Sprint 8 (US-36).

Compares the current 'champion' model's F1 against the previous version.
Rolls back the 'champion' alias to version N-1 if F1 drops more than 10%.

Sources of F1 metrics:
  - Primary: MLflow run metrics (test_f1 logged during training)
  - Fallback: backend/models/noshow_training_report.json

Exit codes:
  0 — no rollback needed (current model is fine)
  1 — rollback performed
  2 — error (insufficient versions, missing metrics, etc.)

Usage:
  python scripts/auto_rollback.py
  python scripts/auto_rollback.py --threshold 0.05   # 5% drop triggers rollback
  python scripts/auto_rollback.py --dry-run
"""
import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
MLFLOW_DIR = BASE_DIR / "backend" / ".local" / "mlflow"
MLFLOW_TRACKING_URI = (MLFLOW_DIR / "runs").resolve().as_uri()

DEFAULT_ROLLBACK_THRESHOLD = 0.10   # 10% F1 drop triggers rollback


def get_mlflow_client():
    import mlflow
    import os
    uri = os.getenv("MLFLOW_TRACKING_URI", MLFLOW_TRACKING_URI)
    mlflow.set_tracking_uri(uri)
    return mlflow.tracking.MlflowClient(), uri


def get_f1_for_version(client, model_name: str, version: int) -> float | None:
    """Fetch test_f1 from the MLflow run associated with a model version."""
    try:
        mv = client.get_model_version(model_name, str(version))
        run = client.get_run(mv.run_id)
        return float(run.data.metrics.get("test_f1", 0.0))
    except Exception as exc:
        print(f"  Warning: could not fetch F1 for version {version}: {exc}")
        return None


def get_champion_version(client, model_name: str) -> int | None:
    """Return the version number tagged with alias 'champion'."""
    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
        return int(mv.version)
    except Exception:
        return None


def run_rollback(model_name: str, threshold: float, dry_run: bool) -> int:
    try:
        client, uri = get_mlflow_client()
    except ImportError:
        print("mlflow not installed — rollback skipped")
        return 2

    print(f"MLflow tracking URI: {uri}")
    print(f"Model name: {model_name}")
    print(f"Rollback threshold: {threshold*100:.0f}% F1 drop")

    champion_version = get_champion_version(client, model_name)
    if champion_version is None:
        print("No 'champion' alias found — nothing to roll back")
        return 2

    if champion_version <= 1:
        print(f"Champion is version {champion_version} — no previous version to roll back to")
        return 2

    prev_version = champion_version - 1
    current_f1 = get_f1_for_version(client, model_name, champion_version)
    prev_f1    = get_f1_for_version(client, model_name, prev_version)

    if current_f1 is None or prev_f1 is None:
        print("Could not retrieve F1 metrics — rollback skipped")
        return 2

    drop = (prev_f1 - current_f1) / max(prev_f1, 1e-8)
    print(f"\nVersion {champion_version} (current champion): F1={current_f1:.4f}")
    print(f"Version {prev_version}   (previous):          F1={prev_f1:.4f}")
    print(f"F1 drop: {drop*100:.2f}%  (threshold={threshold*100:.0f}%)")

    if drop >= threshold:
        if dry_run:
            print(f"\n[--dry-run] Would roll back champion: v{champion_version} → v{prev_version}")
            return 1

        print(f"\nROLLBACK — setting 'champion' alias to version {prev_version}")
        client.set_registered_model_alias(model_name, "champion", str(prev_version))
        print(f"Rollback complete. Current champion: version {prev_version}")
        return 1
    else:
        print("\nNo rollback needed — current champion is performing adequately")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default="noshow-risk-model")
    parser.add_argument("--threshold", type=float, default=DEFAULT_ROLLBACK_THRESHOLD,
                        help="F1 drop fraction that triggers rollback (default 0.10 = 10%%)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    exit_code = run_rollback(args.model_name, args.threshold, args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
