"""
Tests for US-01: health endpoint responds 200 in < 2 seconds.
"""
import time
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """Health endpoint must return HTTP 200."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_time(client):
    """US-01 acceptance criterion: response in < 2 seconds."""
    start = time.time()
    response = await client.get("/api/v1/health")
    elapsed = time.time() - start
    assert response.status_code == 200
    assert elapsed < 2.0, f"Health check took {elapsed:.2f}s — must be < 2s"


@pytest.mark.asyncio
async def test_health_response_structure(client):
    """Health response must include status and services fields."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "postgres" in data["services"]
    assert "redis" in data["services"]


@pytest.mark.asyncio
async def test_health_status_values(client):
    """Health status must be 'healthy' or 'degraded', never arbitrary string."""
    response = await client.get("/api/v1/health")
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
