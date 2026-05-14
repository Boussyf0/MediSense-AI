"""
Airflow DAG — Weekly No-Show Model Retraining (Sprint 8, US-34).

Schedule: every Monday at 02:00 UTC
Tasks:
  1. export_training_data  — PostgreSQL → CSV (rolling 12 months)
  2. train_noshow_model    — runs scripts/train_noshow.py
  3. quality_gate          — F1 >= 0.80 and AUC >= 0.87
  4. register_model        — promotes to MLflow Registry alias "champion"
  5. run_drift_detection   — Evidently PSI report vs previous reference window

Requires:
  - MEDISENSE_DB_URL env var (PostgreSQL connection string)
  - MLFLOW_TRACKING_URI env var
  - Python path includes /opt/medisense/backend
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

BACKEND_DIR = Path(os.getenv("MEDISENSE_BACKEND_DIR", "/opt/medisense/backend"))
SCRIPTS_DIR = BACKEND_DIR / "scripts"
DATA_DIR    = BACKEND_DIR / "data"
MODEL_DIR   = BACKEND_DIR / "models"

DEFAULT_ARGS = {
    "owner": "medisense-mlops",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def export_training_data(**context) -> str:
    """Export the last 12 months of appointment data to CSV for retraining."""
    import psycopg2
    import pandas as pd

    db_url = os.environ["MEDISENSE_DB_URL"]
    output_path = DATA_DIR / "noshow_retrain_data.csv"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(db_url)
    try:
        query = """
            SELECT
                appointment_uuid,
                extract(hour FROM scheduled_at)::int           AS hour_of_day,
                extract(dow  FROM scheduled_at)::int           AS day_of_week,
                extract(month FROM scheduled_at)::int          AS month,
                COALESCE(lead_time_days, 0)                    AS lead_time_days,
                COALESCE(patient_noshow_count_12m, 0)          AS patient_noshow_count_12m,
                COALESCE(patient_appointment_count_12m, 1)     AS patient_appointment_count_12m,
                specialty,
                'M'                                            AS sex,
                30                                             AS patient_age,
                0                                             AS sms_sent,
                CASE WHEN status = 'NO_SHOW' THEN 1 ELSE 0 END AS is_noshow
            FROM appointments
            WHERE scheduled_at >= NOW() - INTERVAL '12 months'
              AND status IN ('COMPLETED', 'NO_SHOW')
            ORDER BY scheduled_at DESC
        """
        df = pd.read_sql(query, conn)
        df.to_csv(output_path, index=False)
        print(f"Exported {len(df)} rows to {output_path}")
    finally:
        conn.close()

    context["ti"].xcom_push(key="data_path", value=str(output_path))
    return str(output_path)


def train_noshow_model(**context) -> None:
    """Run train_noshow.py — uses the exported CSV."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "train_noshow.py")],
        cwd=str(BACKEND_DIR),
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Training failed:\n{result.stderr}")


def quality_gate(**context) -> None:
    """Assert the trained model meets F1 and AUC thresholds."""
    report_path = MODEL_DIR / "noshow_training_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"No report at {report_path}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    metrics = report["test_metrics"]
    f1  = float(metrics["f1"])
    auc = float(metrics["auc"])

    f1_thresh  = float(os.getenv("MLFLOW_PROMOTION_F1_THRESHOLD",  "0.80"))
    auc_thresh = float(os.getenv("MLFLOW_PROMOTION_AUC_THRESHOLD", "0.87"))

    print(f"Quality gate: F1={f1:.4f} (>={f1_thresh}), AUC={auc:.4f} (>={auc_thresh})")
    if f1 < f1_thresh or auc < auc_thresh:
        raise ValueError(
            f"QUALITY GATE FAILED — F1={f1:.4f} (need >={f1_thresh}), "
            f"AUC={auc:.4f} (need >={auc_thresh})"
        )


def register_model(**context) -> None:
    """Promote the newly trained model to MLflow Registry alias 'champion'."""
    report_path = MODEL_DIR / "noshow_training_report.json"
    run_id = json.loads(report_path.read_text())["mlflow_run_id"]

    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "register_noshow_model.py"),
         "--run-id", run_id, "--alias", "champion"],
        cwd=str(BACKEND_DIR), capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(f"Registration failed:\n{result.stderr}")


def run_drift_detection(**context) -> None:
    """Run Evidently drift detection after retraining."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "detect_drift.py")],
        cwd=str(BACKEND_DIR), capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(BACKEND_DIR)},
    )
    print(result.stdout)
    # Drift is a warning, not a hard failure — don't raise on non-zero


with DAG(
    dag_id="medisense_retrain_noshow_weekly",
    default_args=DEFAULT_ARGS,
    description="Weekly no-show model retraining with quality gate and drift detection",
    schedule_interval="0 2 * * 1",  # Monday 02:00 UTC
    start_date=datetime(2026, 7, 6),
    catchup=False,
    tags=["mlops", "no-show", "sprint8"],
) as dag:

    t_export = PythonOperator(
        task_id="export_training_data",
        python_callable=export_training_data,
    )
    t_train = PythonOperator(
        task_id="train_noshow_model",
        python_callable=train_noshow_model,
    )
    t_gate = PythonOperator(
        task_id="quality_gate",
        python_callable=quality_gate,
    )
    t_register = PythonOperator(
        task_id="register_model",
        python_callable=register_model,
    )
    t_drift = PythonOperator(
        task_id="run_drift_detection",
        python_callable=run_drift_detection,
    )

    t_export >> t_train >> t_gate >> t_register >> t_drift
