"""
WebSocket connection manager — Sprint 7 (US-54).

Single-process pub/sub for real-time anomaly alerts. Tracks WebSocket
connections grouped by recipient role (e.g. "doctor", "secretary") and
broadcasts JSON payloads to every connection in a target group.

Limitation: in-process only. To scale beyond one FastAPI replica, swap
the per-role list for Redis pub/sub channels. Documented as a TODO.
"""
import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # role → list of active sockets
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, role: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[role].append(websocket)
        self._publish_gauge(role)
        logger.info("WS connected: role=%s total=%d", role, len(self._connections[role]))

    async def disconnect(self, role: str, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections[role]:
                self._connections[role].remove(websocket)
        self._publish_gauge(role)
        logger.info("WS disconnected: role=%s remaining=%d", role, len(self._connections[role]))

    def _publish_gauge(self, role: str) -> None:
        try:
            from app.api.v1.endpoints.metrics import ws_active_connections
            ws_active_connections.labels(role=role).set(len(self._connections.get(role, [])))
        except Exception:
            pass

    async def broadcast(self, role: str, payload: dict[str, Any]) -> int:
        """
        Send `payload` to every socket subscribed to `role`. Returns the
        number of successful deliveries. Dead sockets are pruned silently.
        """
        targets = list(self._connections.get(role, []))
        if not targets:
            return 0

        sent = 0
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
                sent += 1
            except Exception as exc:  # pragma: no cover
                logger.debug("WS send failed (will prune): %s", exc)
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections[role]:
                        self._connections[role].remove(ws)

        return sent

    def connection_count(self, role: str | None = None) -> int:
        if role is None:
            return sum(len(v) for v in self._connections.values())
        return len(self._connections.get(role, []))


# Singleton — imported by anomaly_detector and the WebSocket endpoint
manager = ConnectionManager()
