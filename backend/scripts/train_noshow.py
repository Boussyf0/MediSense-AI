import json
from pathlib import Path
from typing import Any

import catboost as cb
import joblib
import lightgbm as lgb
import matplotlib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import optuna
import pandas as pd
import shap
import xgboost as xgb
from imblearn.over_sampling import SMOTE
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, classification_report, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

matplotlib.use("Agg")

# Configuration
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "backend" / "data" / "noshow_synthetic_data.csv"
MODEL_DIR = BASE_DIR / "backend" / "models"
MLFLOW_DIR = BASE_DIR / "backend" / ".local" / "mlflow"
MLFLOW_RUNS_DIR = MLFLOW_DIR / "runs"
MLFLOW_TRACKING_URI = MLFLOW_RUNS_DIR.resolve().as_uri()
EXPERIMENT_NAME = "No-Show-Prediction-Sprint5"
RANDOM_STATE = 42


def configure_mlflow() -> None:
    MLFLOW_DIR.mkdir(parents=True, exist_ok=True)
    MLFLOW_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)


def extract_features_and_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = df.drop(columns=["appointment_uuid", "is_noshow"]).copy()
    y = df["is_noshow"].copy()
    return X, y


def fit_preprocessors(X_train_raw: pd.DataFrame) -> tuple[pd.DataFrame, LabelEncoder, StandardScaler]:
    X_train = X_train_raw.copy()
    label_encoder = LabelEncoder()
    X_train["sex"] = label_encoder.fit_transform(X_train["sex"])

    scaler = StandardScaler()
    X_scaled = pd.DataFrame(
        scaler.fit_transform(X_train),
        columns=X_train.columns,
        index=X_train.index,
    )
    return X_scaled, label_encoder, scaler


def transform_features(
    X_raw: pd.DataFrame,
    label_encoder: LabelEncoder,
    scaler: StandardScaler,
) -> pd.DataFrame:
    X = X_raw.copy()
    X["sex"] = label_encoder.transform(X["sex"])
    return pd.DataFrame(
        scaler.transform(X),
        columns=X.columns,
        index=X.index,
    )


def objective(trial: optuna.Trial, X: pd.DataFrame, y: pd.Series) -> float:
    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }

    skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)
    scores: list[float] = []

    for train_idx, val_idx in skf.split(X, y):
        X_train_fold_raw, X_val_fold_raw = X.iloc[train_idx], X.iloc[val_idx]
        y_train_fold, y_val_fold = y.iloc[train_idx], y.iloc[val_idx]

        X_train_fold, fold_encoder, fold_scaler = fit_preprocessors(X_train_fold_raw)
        X_val_fold = transform_features(X_val_fold_raw, fold_encoder, fold_scaler)

        smote = SMOTE(k_neighbors=5, random_state=RANDOM_STATE)
        X_resampled, y_resampled = smote.fit_resample(X_train_fold, y_train_fold)

        model = xgb.XGBClassifier(**params)
        model.fit(X_resampled, y_resampled, eval_set=[(X_val_fold, y_val_fold)], verbose=False)

        predictions = model.predict(X_val_fold)
        scores.append(f1_score(y_val_fold, predictions))

    return float(np.mean(scores))


def get_candidate_models(best_xgb_params: dict[str, Any]) -> dict[str, Any]:
    return {
        "xgboost": xgb.XGBClassifier(**best_xgb_params, random_state=RANDOM_STATE, n_jobs=-1),
        "lightgbm": lgb.LGBMClassifier(
            n_estimators=500,
            learning_rate=0.05,
            max_depth=-1,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbosity=-1,
        ),
        "catboost": cb.CatBoostClassifier(
            iterations=500,
            depth=6,
            learning_rate=0.05,
            random_seed=RANDOM_STATE,
            verbose=False,
        ),
    }


def cross_validate_with_smote(model: Any, X: pd.DataFrame, y: pd.Series) -> tuple[float, float]:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    f1_scores: list[float] = []
    auc_scores: list[float] = []

    for train_idx, val_idx in skf.split(X, y):
        X_train_fold_raw, X_val_fold_raw = X.iloc[train_idx], X.iloc[val_idx]
        y_train_fold, y_val_fold = y.iloc[train_idx], y.iloc[val_idx]

        X_train_fold, fold_encoder, fold_scaler = fit_preprocessors(X_train_fold_raw)
        X_val_fold = transform_features(X_val_fold_raw, fold_encoder, fold_scaler)

        smote = SMOTE(k_neighbors=5, random_state=RANDOM_STATE)
        X_resampled, y_resampled = smote.fit_resample(X_train_fold, y_train_fold)

        fold_model = clone(model)
        fold_model.fit(X_resampled, y_resampled)

        predictions = fold_model.predict(X_val_fold)
        probabilities = fold_model.predict_proba(X_val_fold)[:, 1]

        f1_scores.append(f1_score(y_val_fold, predictions))
        auc_scores.append(roc_auc_score(y_val_fold, probabilities))

    return float(np.mean(f1_scores)), float(np.mean(auc_scores))


def expected_calibration_error(
    y_true: pd.Series,
    probabilities: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Estimate how closely predicted probabilities match observed rates."""
    y_values = y_true.to_numpy(dtype=float)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0

    for lower, upper in zip(bin_edges[:-1], bin_edges[1:]):
        if upper == 1.0:
            in_bin = (probabilities >= lower) & (probabilities <= upper)
        else:
            in_bin = (probabilities >= lower) & (probabilities < upper)
        if not np.any(in_bin):
            continue

        bin_weight = float(np.mean(in_bin))
        bin_accuracy = float(np.mean(y_values[in_bin]))
        bin_confidence = float(np.mean(probabilities[in_bin]))
        ece += bin_weight * abs(bin_accuracy - bin_confidence)

    return float(ece)


def run_training() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    X_raw, y = extract_features_and_target(df)

    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )
    X_train, label_encoder, scaler = fit_preprocessors(X_train_raw)
    X_test = transform_features(X_test_raw, label_encoder, scaler)

    configure_mlflow()

    with mlflow.start_run():
        print("Optimizing XGBoost with Optuna...")
        study = optuna.create_study(direction="maximize")
        study.optimize(lambda trial: objective(trial, X_train_raw, y_train), n_trials=20)
        best_xgb_params = study.best_params
        mlflow.log_params(best_xgb_params)

        models = get_candidate_models(best_xgb_params)
        benchmark: dict[str, dict[str, float]] = {}

        print("Running 5-fold benchmark with SMOTE...")
        for model_name, model in models.items():
            cv_f1, cv_auc = cross_validate_with_smote(model, X_train_raw, y_train)
            benchmark[model_name] = {"cv_f1": cv_f1, "cv_auc": cv_auc}
            mlflow.log_metric(f"cv_f1_{model_name}", cv_f1)
            mlflow.log_metric(f"cv_auc_{model_name}", cv_auc)
            print(f"{model_name}: F1={cv_f1:.4f}, AUC={cv_auc:.4f}")

        winner_model_name = max(
            benchmark,
            key=lambda name: (benchmark[name]["cv_f1"], benchmark[name]["cv_auc"]),
        )
        winner_template = models[winner_model_name]
        print(f"Winner model: {winner_model_name}")

        smote = SMOTE(k_neighbors=5, random_state=RANDOM_STATE)
        X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)

        winner_model = clone(winner_template)
        winner_model.fit(X_train_resampled, y_train_resampled)

        test_predictions = winner_model.predict(X_test)
        test_probabilities = winner_model.predict_proba(X_test)[:, 1]
        test_f1 = f1_score(y_test, test_predictions)
        test_auc = roc_auc_score(y_test, test_probabilities)
        test_brier = brier_score_loss(y_test, test_probabilities)
        test_ece = expected_calibration_error(y_test, test_probabilities)

        mlflow.log_metric("test_f1", float(test_f1))
        mlflow.log_metric("test_auc", float(test_auc))
        mlflow.log_metric("test_brier", float(test_brier))
        mlflow.log_metric("test_ece", float(test_ece))
        print("\nTest Set Report:")
        print(classification_report(y_test, test_predictions))
        print(f"Calibration: Brier={test_brier:.4f}, ECE={test_ece:.4f}")

        print("Generating SHAP explainer...")
        explainer = shap.TreeExplainer(winner_model)

        model_output_path = MODEL_DIR / "noshow_model.joblib"
        explainer_output_path = MODEL_DIR / "noshow_shap_explainer.joblib"
        scaler_output_path = MODEL_DIR / "noshow_scaler.joblib"
        encoder_output_path = MODEL_DIR / "noshow_label_encoder.joblib"
        report_output_path = MODEL_DIR / "noshow_training_report.json"

        joblib.dump(winner_model, model_output_path)
        joblib.dump(explainer, explainer_output_path)
        joblib.dump(scaler, scaler_output_path)
        joblib.dump(label_encoder, encoder_output_path)

        training_report = {
            "winner_model": winner_model_name,
            "benchmark": benchmark,
            "test_metrics": {"f1": float(test_f1), "auc": float(test_auc)},
            "calibration": {
                "brier_score": float(test_brier),
                "expected_calibration_error": float(test_ece),
                "n_bins": 10,
            },
        }
        with open(report_output_path, "w", encoding="utf-8") as fp:
            json.dump(training_report, fp, indent=2)

        mlflow.log_artifact(str(report_output_path), artifact_path="reports")

        fraction_pos, mean_pred = calibration_curve(y_test, test_probabilities, n_bins=10, strategy="uniform")
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.plot([0, 1], [0, 1], "k--", label="Perfect calibration")
        ax.plot(mean_pred, fraction_pos, "s-", label=f"{winner_model_name} (Brier={test_brier:.3f}, ECE={test_ece:.3f})")
        ax.set_xlabel("Mean predicted probability")
        ax.set_ylabel("Fraction of positives")
        ax.set_title("Calibration Curve — No-Show Model")
        ax.legend()
        ax.grid(alpha=0.3)
        calibration_plot_path = MODEL_DIR / "calibration_curve.png"
        fig.savefig(calibration_plot_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        mlflow.log_artifact(str(calibration_plot_path), artifact_path="plots")

        mlflow.sklearn.log_model(winner_model, artifact_path="model")
        print(f"Model and artifacts saved to {MODEL_DIR}")


if __name__ == "__main__":
    run_training()
