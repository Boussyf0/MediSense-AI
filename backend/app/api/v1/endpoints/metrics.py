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


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint — consumed by monitoring stack."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
