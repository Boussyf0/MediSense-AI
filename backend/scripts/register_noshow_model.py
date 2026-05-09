"""
MLflow Model Registry — promotion script (Sprint 6, US-33).

Usage:
  python scripts/register_noshow_model.py \\
      --run-id <mlflow_run_id> \\
      --alias champion               # promotes run to production alias
      [--force]                      # skip quality gate
      [--dry-run]                    # show what would happen, do not act

Promotion criteria (enforced unless --force):
  test_f1  >= MLFLOW_PROMOTION_F1_THRESHOLD  (default 0.80)
  test_auc >= MLFLOW_PROMOTION_AUC_THRESHOLD (default 0.87)

Aliases:
  champion   → production (served by inference service)
  challenger → candidate (A/B testing, shadow traffic)

Tracking URI resolution order:
  1. --tracking-uri CLI argument
  2. MLFLOW_TRACKING_URI environment variable
  3. Local file URI: backend/.local/mlflow/runs/
"""
import argparse
import os
import sys
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient


def configure_mlflow(tracking_uri: str) -> MlflowClient:
    mlflow.set_tracking_uri(tracking_uri)
    return MlflowClient()


def get_quality_gate_metrics(client: MlflowClient, run_id: str) -> dict:
    """Fetch test_f1 and test_auc from the MLflow run."""
    run = client.get_run(run_id)
    metrics = run.data.metrics
    return {
        "test_f1": float(metrics.get("test_f1", 0.0)),
        "test_auc": float(metrics.get("test_auc", 0.0)),
    }


def check_promotion_criteria(
    metrics: dict, f1_threshold: float, auc_threshold: float
) -> bool:
    return metrics["test_f1"] >= f1_threshold and metrics["test_auc"] >= auc_threshold


def promote_model(
    client: MlflowClient, model_name: str, run_id: str, alias: str
) -> str:
    """Register run to model registry and assign alias. Returns version string."""
    model_uri = f"runs:/{run_id}/model"
    mv = mlflow.register_model(model_uri, model_name)
    client.set_registered_model_alias(model_name, alias, mv.version)
    return mv.version


def _resolve_tracking_uri(cli_uri: str) -> str:
    if cli_uri:
        return cli_uri
    env_uri = os.getenv("MLFLOW_TRACKING_URI", "")
    if env_uri:
        return env_uri
    local_path = Path(__file__).resolve().parents[1] / ".local" / "mlflow" / "runs"
    return local_path.as_uri()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote a MLflow run to the noshow-risk-model registry"
    )
    parser.add_argument("--run-id", required=True, help="MLflow run ID to register")
    parser.add_argument(
        "--alias", default="champion", choices=["champion", "challenger"],
        help="Registry alias to assign (default: champion)"
    )
    parser.add_argument(
        "--model-name", default="noshow-risk-model",
        help="Registered model name (default: noshow-risk-model)"
    )
    parser.add_argument("--tracking-uri", default="", help="MLflow tracking URI")
    parser.add_argument(
        "--f1-threshold", type=float, default=0.80,
        help="Minimum test_f1 required for promotion (default: 0.80)"
    )
    parser.add_argument(
        "--auc-threshold", type=float, default=0.87,
        help="Minimum test_auc required for promotion (default: 0.87)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip quality gate and promote regardless of metrics"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without registering"
    )
    args = parser.parse_args()

    tracking_uri = _resolve_tracking_uri(args.tracking_uri)
    client = configure_mlflow(tracking_uri)

    metrics = get_quality_gate_metrics(client, args.run_id)
    print(
        f"Run {args.run_id}: "
        f"test_f1={metrics['test_f1']:.4f}  test_auc={metrics['test_auc']:.4f}"
    )

    if not args.force:
        if not check_promotion_criteria(metrics, args.f1_threshold, args.auc_threshold):
            print(
                f"QUALITY GATE FAILED: required test_f1 >= {args.f1_threshold} "
                f"AND test_auc >= {args.auc_threshold}"
            )
            sys.exit(1)

    if args.dry_run:
        print(
            f"[dry-run] Would promote run {args.run_id} "
            f"to alias '{args.alias}' on model '{args.model_name}'"
        )
        sys.exit(0)

    version = promote_model(client, args.model_name, args.run_id, args.alias)
    print(f"Promoted version {version} to alias '{args.alias}'")
    print(f"Model URI: models:/{args.model_name}@{args.alias}")


if __name__ == "__main__":
    main()
