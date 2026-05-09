"""
Tests for MLflow Model Registry promotion script — Sprint 6, US-33.

Pure unit tests — no DB fixtures, no real MLflow server.
All MlflowClient calls and mlflow.register_model are mocked.

mlflow is not guaranteed to be installed in the dev venv, so we inject
a stub into sys.modules before the script module is first imported.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

# ── Stub mlflow + mlflow.tracking before the script is imported ──────────────
_mlflow_stub = MagicMock()
_mlflow_tracking_stub = MagicMock()
sys.modules.setdefault("mlflow", _mlflow_stub)
sys.modules.setdefault("mlflow.tracking", _mlflow_tracking_stub)
# Expose MlflowClient on the stub so `from mlflow.tracking import MlflowClient` works
_mlflow_tracking_stub.MlflowClient = MagicMock


def _make_client_with_metrics(test_f1: float, test_auc: float) -> MagicMock:
    client = MagicMock()
    run = MagicMock()
    run.data.metrics = {"test_f1": test_f1, "test_auc": test_auc}
    client.get_run.return_value = run
    return client


# ── Quality gate ──────────────────────────────────────────────────────────────

class TestQualityGate:
    """check_promotion_criteria enforces >= (inclusive) thresholds."""

    def test_passes_when_both_above_threshold(self):
        from scripts.register_noshow_model import check_promotion_criteria
        assert check_promotion_criteria({"test_f1": 0.85, "test_auc": 0.90}, 0.80, 0.87) is True

    def test_fails_when_f1_too_low(self):
        from scripts.register_noshow_model import check_promotion_criteria
        assert check_promotion_criteria({"test_f1": 0.75, "test_auc": 0.90}, 0.80, 0.87) is False

    def test_fails_when_auc_too_low(self):
        from scripts.register_noshow_model import check_promotion_criteria
        assert check_promotion_criteria({"test_f1": 0.85, "test_auc": 0.80}, 0.80, 0.87) is False

    def test_boundary_exact_threshold_passes(self):
        """Boundary: exactly == threshold must pass (>= not >)."""
        from scripts.register_noshow_model import check_promotion_criteria
        assert check_promotion_criteria({"test_f1": 0.80, "test_auc": 0.87}, 0.80, 0.87) is True

    def test_boundary_one_below_fails(self):
        from scripts.register_noshow_model import check_promotion_criteria
        assert check_promotion_criteria({"test_f1": 0.7999, "test_auc": 0.87}, 0.80, 0.87) is False

    def test_get_quality_gate_metrics_extracts_from_run(self):
        from scripts.register_noshow_model import get_quality_gate_metrics
        client = _make_client_with_metrics(0.82, 0.88)
        metrics = get_quality_gate_metrics(client, "run-abc")
        assert metrics["test_f1"] == pytest.approx(0.82)
        assert metrics["test_auc"] == pytest.approx(0.88)
        client.get_run.assert_called_once_with("run-abc")

    def test_missing_metrics_default_to_zero(self):
        """If run lacks test_f1/test_auc, they default to 0.0 — gate fails."""
        from scripts.register_noshow_model import get_quality_gate_metrics
        client = MagicMock()
        run = MagicMock()
        run.data.metrics = {}   # no metrics logged
        client.get_run.return_value = run
        metrics = get_quality_gate_metrics(client, "run-xyz")
        assert metrics["test_f1"] == 0.0
        assert metrics["test_auc"] == 0.0


# ── promote_model ─────────────────────────────────────────────────────────────

class TestPromoteModel:
    """promote_model registers run to registry and assigns the alias."""

    def test_registers_and_sets_alias(self):
        from scripts.register_noshow_model import promote_model

        client = MagicMock()
        mv = MagicMock()
        mv.version = "3"
        client.set_registered_model_alias = MagicMock()

        with patch("scripts.register_noshow_model.mlflow.register_model", return_value=mv) as mock_reg:
            version = promote_model(client, "noshow-risk-model", "run-123", "champion")

        mock_reg.assert_called_once_with("runs:/run-123/model", "noshow-risk-model")
        client.set_registered_model_alias.assert_called_once_with(
            "noshow-risk-model", "champion", "3"
        )
        assert version == "3"

    def test_challenger_alias_assigned(self):
        from scripts.register_noshow_model import promote_model

        client = MagicMock()
        mv = MagicMock()
        mv.version = "7"

        with patch("scripts.register_noshow_model.mlflow.register_model", return_value=mv):
            promote_model(client, "noshow-risk-model", "run-456", "challenger")

        client.set_registered_model_alias.assert_called_once_with(
            "noshow-risk-model", "challenger", "7"
        )


# ── main() CLI behaviour ──────────────────────────────────────────────────────

class TestMainCLI:
    """End-to-end tests for the argparse main() function."""

    BASE_ARGS = [
        "register_noshow_model.py",
        "--run-id", "run-abc123",
    ]

    def _run_main(self, extra_args: list[str], client: MagicMock) -> None:
        with patch("sys.argv", self.BASE_ARGS + extra_args), \
             patch("scripts.register_noshow_model.configure_mlflow", return_value=client):
            from scripts.register_noshow_model import main
            main()

    def test_exits_1_on_gate_failure(self):
        """Gate fails (low metrics) → sys.exit(1)."""
        client = _make_client_with_metrics(0.50, 0.60)
        with pytest.raises(SystemExit) as exc_info:
            self._run_main([], client)
        assert exc_info.value.code == 1

    def test_dry_run_exits_0_without_registering(self):
        """--dry-run: quality gate may pass, but mlflow.register_model must NOT be called."""
        client = _make_client_with_metrics(0.82, 0.90)

        with patch("scripts.register_noshow_model.mlflow.register_model") as mock_reg, \
             patch("sys.argv", self.BASE_ARGS + ["--dry-run"]), \
             patch("scripts.register_noshow_model.configure_mlflow", return_value=client):
            from scripts.register_noshow_model import main
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        mock_reg.assert_not_called()

    def test_force_skips_gate_and_promotes(self):
        """--force promotes even when metrics are below threshold."""
        client = _make_client_with_metrics(0.50, 0.60)
        mv = MagicMock()
        mv.version = "2"
        client.set_registered_model_alias = MagicMock()

        with patch("scripts.register_noshow_model.mlflow.register_model", return_value=mv) as mock_reg, \
             patch("sys.argv", self.BASE_ARGS + ["--force"]), \
             patch("scripts.register_noshow_model.configure_mlflow", return_value=client):
            from scripts.register_noshow_model import main
            main()   # must not raise or sys.exit(1)

        mock_reg.assert_called_once()

    def test_custom_thresholds_respected(self):
        """--f1-threshold and --auc-threshold override defaults."""
        client = _make_client_with_metrics(0.70, 0.75)

        # With default thresholds (0.80 / 0.87) this would fail.
        # With custom thresholds (0.65 / 0.70) it must pass.
        mv = MagicMock()
        mv.version = "5"
        client.set_registered_model_alias = MagicMock()

        with patch("scripts.register_noshow_model.mlflow.register_model", return_value=mv), \
             patch("sys.argv", self.BASE_ARGS + ["--f1-threshold", "0.65", "--auc-threshold", "0.70"]), \
             patch("scripts.register_noshow_model.configure_mlflow", return_value=client):
            from scripts.register_noshow_model import main
            main()   # must not raise

        client.set_registered_model_alias.assert_called_once()


# ── Tracking URI resolution ───────────────────────────────────────────────────

class TestTrackingURIResolution:
    """_resolve_tracking_uri respects CLI → env → local-file fallback order."""

    def test_cli_arg_takes_priority(self):
        from scripts.register_noshow_model import _resolve_tracking_uri
        uri = _resolve_tracking_uri("http://mlflow.custom/")
        assert uri == "http://mlflow.custom/"

    def test_env_var_used_when_no_cli(self):
        from scripts.register_noshow_model import _resolve_tracking_uri
        with patch.dict("os.environ", {"MLFLOW_TRACKING_URI": "http://env-mlflow/"}):
            uri = _resolve_tracking_uri("")
        assert uri == "http://env-mlflow/"

    def test_local_file_fallback(self, tmp_path):
        from scripts.register_noshow_model import _resolve_tracking_uri
        with patch.dict("os.environ", {}, clear=False):
            # Remove env var if present
            import os
            os.environ.pop("MLFLOW_TRACKING_URI", None)
            uri = _resolve_tracking_uri("")
        assert uri.startswith("file://")
        assert "mlflow" in uri


# ── NoShowPredictor version string ───────────────────────────────────────────

class TestPredictorVersionString:
    """
    Verify that _load_models() builds the correct version string when
    noshow_training_report.json contains mlflow_run_id.
    """

    def test_version_includes_run_id_prefix(self, tmp_path):
        """v6.0-{winner}-run{run_id[:8]} when mlflow_run_id present."""
        import json
        report = {
            "winner_model": "xgboost",
            "mlflow_run_id": "abcdef1234567890",
            "benchmark": {},
            "test_metrics": {"f1": 0.82, "auc": 0.88},
        }
        report_path = tmp_path / "noshow_training_report.json"
        report_path.write_text(json.dumps(report))

        from app.services.noshow_predictor import NoShowPredictor

        fake_artifact = MagicMock()
        with patch("app.services.noshow_predictor.METADATA_PATH", report_path), \
             patch("app.services.noshow_predictor.MODELS_DIR", tmp_path), \
             patch("app.services.noshow_predictor.joblib.load", return_value=fake_artifact):
            predictor = object.__new__(NoShowPredictor)
            predictor._load_models()

        assert predictor.model_version == "v6.0-xgboost-runabcdef12"

    def test_version_fallback_without_run_id(self, tmp_path):
        """v5.1-{winner} when mlflow_run_id is absent from report."""
        import json
        report = {
            "winner_model": "lightgbm",
            "benchmark": {},
            "test_metrics": {"f1": 0.81, "auc": 0.89},
        }
        report_path = tmp_path / "noshow_training_report.json"
        report_path.write_text(json.dumps(report))

        from app.services.noshow_predictor import NoShowPredictor

        fake_artifact = MagicMock()
        with patch("app.services.noshow_predictor.METADATA_PATH", report_path), \
             patch("app.services.noshow_predictor.MODELS_DIR", tmp_path), \
             patch("app.services.noshow_predictor.joblib.load", return_value=fake_artifact):
            predictor = object.__new__(NoShowPredictor)
            predictor._load_models()

        assert predictor.model_version == "v5.1-lightgbm"
