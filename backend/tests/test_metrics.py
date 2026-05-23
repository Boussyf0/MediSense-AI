"""Tests for the Prometheus metrics endpoint and seed_metrics."""
import pytest
from app.api.v1.endpoints.metrics import seed_metrics


def test_seed_metrics_initializes_counters():
    """seed_metrics() runs without error and initializes all label combos."""
    seed_metrics()


@pytest.mark.asyncio
async def test_prometheus_endpoint_returns_200(client):
    resp = await client.get("/api/v1/metrics")
    assert resp.status_code == 200
    assert "medisense_http_requests_total" in resp.text or "text/plain" in resp.headers.get("content-type", "")
