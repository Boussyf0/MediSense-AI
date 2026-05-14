#!/usr/bin/env python3
"""
Evidently AI Drift Detection — Sprint 8 (US-35).

Compares the current week's no-show feature distribution against a 4-week
rolling reference window.  Raises an alert if PSI > threshold on >= 2 features.

Output:
  results/drift_report_{YYYYMMDD}.html   — full Evidently HTML report
  results/drift_summary_{YYYYMMDD}.json  — machine-readable summary

Usage:
  python scripts/detect_drift.py                   # uses real DB data
  python scripts/detect_drift.py --dry-run         # uses synthetic data, no DB
  python scripts/detect_drift.py --threshold 0.20  # override PSI threshold
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR    = Path(__file__).resolve().parents[2]
RESULT_DIR  = BASE_DIR / "backend" / "results"
DATA_DIR    = BASE_DIR / "backend" / "data"

FEATURES = [
    "hour_of_day", "day_of_week", "month",
    "lead_time_days", "patient_noshow_count_12m",
    "patient_appointment_count_12m", "patient_age",
]

DEFAULT_PSI_THRESHOLD = float(__import__("os").getenv("EVIDENTLY_PSI_THRESHOLD", "0.25"))


def _load_from_db(weeks_back_start: int, weeks_back_end: int) -> pd.DataFrame:
    """Load appointment features from PostgreSQL for a date window."""
    import psycopg2
    import os

    db_url = os.environ.get("MEDISENSE_DB_URL", "")
    if not db_url:
        raise ValueError("MEDISENSE_DB_URL not set")

    conn = psycopg2.connect(db_url)
    try:
        query = f"""
            SELECT
                extract(hour  FROM scheduled_at)::int AS hour_of_day,
                extract(dow   FROM scheduled_at)::int AS day_of_week,
                extract(month FROM scheduled_at)::int AS month,
                COALESCE(lead_time_days, 0)           AS lead_time_days,
                COALESCE(patient_noshow_count_12m, 0) AS patient_noshow_count_12m,
                COALESCE(patient_appointment_count_12m, 1) AS patient_appointment_count_12m,
                30                                    AS patient_age,
                CASE WHEN status = 'NO_SHOW' THEN 1 ELSE 0 END AS is_noshow
            FROM appointments
            WHERE scheduled_at >= NOW() - INTERVAL '{weeks_back_start} weeks'
              AND scheduled_at <  NOW() - INTERVAL '{weeks_back_end} weeks'
              AND status IN ('COMPLETED', 'NO_SHOW')
        """
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df


def _synthetic_dataframe(n: int, seed: int, drift: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shift = 3.0 if drift else 0.0
    return pd.DataFrame({
        "hour_of_day":                   rng.integers(8, 18, n),
        "day_of_week":                   rng.integers(1, 6, n),
        "month":                         rng.integers(1, 12, n),
        "lead_time_days":                rng.integers(0, 30, n) + shift,
        "patient_noshow_count_12m":      rng.integers(0, 5, n),
        "patient_appointment_count_12m": rng.integers(1, 20, n),
        "patient_age":                   rng.integers(18, 80, n) + shift * 5,
        "is_noshow":                     rng.integers(0, 2, n),
    })


def compute_psi(ref: pd.Series, cur: pd.Series, n_bins: int = 10) -> float:
    """Population Stability Index between two distributions."""
    bins = np.histogram_bin_edges(pd.concat([ref, cur]), bins=n_bins)
    ref_counts, _ = np.histogram(ref, bins=bins)
    cur_counts, _ = np.histogram(cur, bins=bins)

    ref_pct = (ref_counts + 1e-8) / len(ref)
    cur_pct = (cur_counts + 1e-8) / len(cur)

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return max(psi, 0.0)


def run_drift_detection(psi_threshold: float, dry_run: bool) -> dict:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().strftime("%Y%m%d")

    if dry_run:
        print("[--dry-run] Using synthetic data")
        ref_df = _synthetic_dataframe(2000, seed=42, drift=False)
        cur_df = _synthetic_dataframe(500,  seed=99, drift=True)
    else:
        try:
            ref_df = _load_from_db(weeks_back_start=8, weeks_back_end=4)
            cur_df = _load_from_db(weeks_back_start=1, weeks_back_end=0)
        except Exception as exc:
            print(f"DB load failed ({exc}) — using synthetic fallback")
            ref_df = _synthetic_dataframe(2000, seed=42)
            cur_df = _synthetic_dataframe(500,  seed=99)

    print(f"Reference: {len(ref_df)} rows  |  Current: {len(cur_df)} rows")

    psi_scores: dict[str, float] = {}
    for feat in FEATURES:
        if feat not in ref_df.columns or feat not in cur_df.columns:
            continue
        psi = compute_psi(pd.Series(ref_df[feat]), pd.Series(cur_df[feat]))
        psi_scores[feat] = round(psi, 4)

    drifted_features = [f for f, p in psi_scores.items() if p > psi_threshold]
    drift_detected   = len(drifted_features) >= 2

    summary = {
        "date": today,
        "psi_threshold": psi_threshold,
        "psi_scores": psi_scores,
        "drifted_features": drifted_features,
        "drift_detected": drift_detected,
        "ref_rows": len(ref_df),
        "cur_rows": len(cur_df),
    }

    summary_path = RESULT_DIR / f"drift_summary_{today}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Evidently HTML report
    try:
        from evidently import ColumnMapping
        from evidently.report import Report
        from evidently.metric_preset import DataDriftPreset

        report = Report(metrics=[DataDriftPreset()])
        column_mapping = ColumnMapping(target="is_noshow", numerical_features=FEATURES)
        report.run(reference_data=ref_df[FEATURES + ["is_noshow"]],
                   current_data=cur_df[FEATURES + ["is_noshow"]],
                   column_mapping=column_mapping)
        html_path = RESULT_DIR / f"drift_report_{today}.html"
        report.save_html(str(html_path))
        print(f"Evidently report saved: {html_path}")
    except ImportError:
        print("evidently not installed — skipping HTML report")

    # Print results
    print(f"\n{'─'*50}")
    print(f"PSI threshold: {psi_threshold}")
    for feat, psi in psi_scores.items():
        flag = " ⚠ DRIFT" if psi > psi_threshold else ""
        print(f"  {feat:<40} PSI={psi:.4f}{flag}")
    print(f"\nDrifted features: {drifted_features}")
    print(f"Summary saved: {summary_path}")

    if drift_detected:
        print("\nDRIFT DETECTED — consider retraining or rollback")
    else:
        print("\nNo significant drift detected")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=DEFAULT_PSI_THRESHOLD)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run_drift_detection(args.threshold, args.dry_run)
    if summary["drift_detected"]:
        sys.exit(2)   # exit 2 = drift warning (not a hard failure)


if __name__ == "__main__":
    main()
