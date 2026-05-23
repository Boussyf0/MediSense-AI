"""
Prometheus metrics endpoint — US-57 (Sprint 10).

Exposes application metrics in OpenMetrics format for Grafana dashboards.
"""
from fastapi import APIRouter, Response
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST,
    REGISTRY,
)

router = APIRouter()

# ── Application Metrics ────────────────────────────────────────
http_requests_total = Counter(
    "medisense_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "medisense_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

rag_requests_total = Counter(
    "medisense_rag_requests_total",
    "Total RAG pipeline invocations",
    ["language", "provider"],
)

noshow_predictions_total = Counter(
    "medisense_noshow_predictions_total",
    "Total no-show predictions served",
    ["risk_level"],  # low / medium / high
)

iot_anomalies_detected_total = Counter(
    "medisense_iot_anomalies_total",
    "Total IoT anomalies detected",
    ["severity", "metric_type"],
)

active_conversations = Gauge(
    "medisense_active_conversations",
    "Number of active patient conversations",
)

# ── ML / RAG / IoT extras (Sprint 7+) ─────────────────────────
prediction_latency_seconds = Histogram(
    "medisense_prediction_latency_seconds",
    "ML inference latency (seconds)",
    ["model"],  # noshow | lstm_anomaly | bilstm_attn
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

rag_retrieval_latency_seconds = Histogram(
    "medisense_rag_retrieval_latency_seconds",
    "RAG retrieval latency (seconds)",
    ["stage"],  # dense | bm25 | rrf | rerank
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

rag_fallback_total = Counter(
    "medisense_rag_fallback_total",
    "RAG fallback events (LLM unavailable, empty retrieval, etc.)",
    ["reason"],
)

ws_active_connections = Gauge(
    "medisense_ws_active_connections",
    "Active WebSocket connections",
    ["role"],
)

fcm_sends_total = Counter(
    "medisense_fcm_sends_total",
    "FCM push attempts",
    ["outcome"],  # success | failure | mock
)

kafka_consumer_lag = Gauge(
    "medisense_kafka_consumer_lag",
    "Kafka consumer lag (messages behind head) per partition",
    ["topic", "partition"],
)

model_age_seconds = Gauge(
    "medisense_model_age_seconds",
    "Seconds since the model artefact was last trained / loaded",
    ["model"],
)

drift_psi = Gauge(
    "medisense_drift_psi",
    "Population Stability Index (PSI) by feature, latest Evidently report",
    ["feature"],
)


def _load_latest_drift_report() -> None:  # pragma: no cover
    """Load the most recent Evidently drift summary into the drift_psi gauge.

    Looks for ``backend/results/drift_summary_*.json`` produced by
    ``scripts/detect_drift.py``. Silent if no report has been generated yet —
    the seeded zero values stay in place so the Grafana panel still renders.
    """
    import json
    import logging
    from pathlib import Path

    log = logging.getLogger(__name__)
    results_dir = Path(__file__).resolve().parents[4] / "results"
    summaries = sorted(results_dir.glob("drift_summary_*.json"))
    if not summaries:
        return
    try:
        latest = json.loads(summaries[-1].read_text(encoding="utf-8"))
        for feat, psi in (latest.get("psi_scores") or {}).items():
            drift_psi.labels(feature=feat).set(float(psi))
        log.info("Loaded drift PSI from %s", summaries[-1].name)
    except Exception as exc:
        log.warning("Failed to load drift report %s: %s", summaries[-1].name, exc)


def seed_metrics() -> None:
    """Initialise label combinations to zero so Grafana panels show 0 instead
    of "No data" before the first real event fires.

    Called once from the FastAPI lifespan startup hook.
    """
    for level in ("low", "medium", "high"):
        noshow_predictions_total.labels(risk_level=level).inc(0)
    for severity, metric_type in (
        ("critical", "lstm_5m"),
        ("trend", "lstm_60m"),
    ):
        iot_anomalies_detected_total.labels(severity=severity, metric_type=metric_type).inc(0)
    for lang in ("fr", "ar", "en"):
        for prov in ("groq", "ollama"):
            rag_requests_total.labels(language=lang, provider=prov).inc(0)
    for reason in ("llm_timeout", "no_documents", "low_confidence"):
        rag_fallback_total.labels(reason=reason).inc(0)
    for outcome in ("success", "failure", "mock"):
        fcm_sends_total.labels(outcome=outcome).inc(0)
    for role in ("doctor", "secretary", "admin", "patient"):
        ws_active_connections.labels(role=role).set(0)
    active_conversations.set(0)

    # Histograms — emit one 0-obs so the *_bucket / *_count / *_sum series
    # exist; otherwise histogram_quantile() returns NaN and Grafana shows
    # "No data" until the very first real observation.
    for model in ("noshow", "lstm_anomaly", "bilstm_attn"):
        prediction_latency_seconds.labels(model=model).observe(0)
    for stage in ("dense", "bm25", "rrf", "rerank"):
        rag_retrieval_latency_seconds.labels(stage=stage).observe(0)

    # Kafka consumer lag — seed all topics we consume so the panel renders.
    for topic in ("iot.vitals", "iot.anomalies", "appointments.events"):
        for partition in ("0", "1", "2"):
            kafka_consumer_lag.labels(topic=topic, partition=partition).set(0)

    # Evidently drift — feature names match scripts/detect_drift.py.
    for feature in (
        "hour_of_day",
        "day_of_week",
        "month",
        "lead_time_days",
        "patient_noshow_count_12m",
        "patient_appointment_count_12m",
        "patient_age",
    ):
        drift_psi.labels(feature=feature).set(0)
    _load_latest_drift_report()

    # Model freshness — exposed by the training scripts in prod; seed to 0
    # (= "just trained") so the panel is not empty in dev.
    for model in ("noshow", "lstm_anomaly", "bilstm_attn"):
        model_age_seconds.labels(model=model).set(0)


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint — consumed by monitoring stack."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
