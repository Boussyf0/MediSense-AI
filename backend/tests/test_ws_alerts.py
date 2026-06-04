"""
WebSocket alerts (US-54) — endpoint + ConnectionManager tests.

Covers:
  - missing token → connection rejected (1008 policy violation)
  - invalid token → connection rejected
  - role mismatch → connection rejected
  - happy path: doctor token connects, broadcast delivers payload
"""
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app


@pytest.fixture
def sync_client():
    return TestClient(app)


def test_ws_rejected_without_token(sync_client):
    with pytest.raises(WebSocketDisconnect):
        with sync_client.websocket_connect("/api/v1/ws/alerts/doctor"):
            pass  # connection should never open


def test_ws_rejected_with_invalid_token(sync_client):
    with pytest.raises(WebSocketDisconnect):
        with sync_client.websocket_connect("/api/v1/ws/alerts/doctor?token=not-a-jwt"):
            pass


def test_ws_rejected_when_role_mismatch(sync_client):
    """Patient token must not be allowed to subscribe to doctor stream."""
    token = create_access_token(subject=str(uuid.uuid4()), role="patient")
    with pytest.raises(WebSocketDisconnect):
        with sync_client.websocket_connect(
            f"/api/v1/ws/alerts/doctor?token={token}"
        ):
            pass


def test_ws_doctor_receives_broadcast(sync_client):
    """Doctor connects → broadcast pushes message → client reads it."""
    from app.core.ws_manager import manager

    token = create_access_token(subject=str(uuid.uuid4()), role="doctor")
    payload = {"type": "anomaly_critical", "patient_uuid": "abc", "score_5m": 0.95}

    with sync_client.websocket_connect(
        f"/api/v1/ws/alerts/doctor?token={token}"
    ) as ws:
        import asyncio

        async def _broadcast():
            await manager.broadcast("doctor", payload)

        asyncio.run(_broadcast())
        received = ws.receive_json()

    assert received == payload


@pytest.mark.asyncio
async def test_connection_manager_prunes_dead_sockets():
    """If a socket raises during send, it must be pruned from the pool."""
    from app.core.ws_manager import ConnectionManager

    mgr = ConnectionManager()
    good = AsyncMock()
    good.send_json = AsyncMock()
    bad = AsyncMock()
    bad.send_json = AsyncMock(side_effect=RuntimeError("closed"))

    # Bypass accept() — inject directly for the test
    mgr._connections["doctor"] = [good, bad]

    sent = await mgr.broadcast("doctor", {"hello": "world"})
    assert sent == 1
    assert mgr.connection_count("doctor") == 1
    assert good in mgr._connections["doctor"]
    assert bad not in mgr._connections["doctor"]


@pytest.mark.asyncio
async def test_connection_manager_counts_and_metric_failure(monkeypatch):
    from app.core.ws_manager import ConnectionManager
    import app.api.v1.endpoints.metrics as metrics

    mgr = ConnectionManager()
    monkeypatch.delattr(metrics, "ws_active_connections", raising=False)

    mgr._publish_gauge("doctor")
    assert await mgr.broadcast("doctor", {"ping": "pong"}) == 0
    assert mgr.connection_count() == 0
