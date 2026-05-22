"""
WebSocket alerts endpoint — Sprint 7 (US-54).

Clinicians and secretaries open a persistent WebSocket and receive
real-time anomaly notifications pushed by `anomaly_detector.ingest_reading`
when an alert_critical fires.

Authentication: JWT passed as the `token` query parameter (browsers
cannot set Authorization headers on WebSocket connections). The token
is decoded with the same secret as REST endpoints; expired or
tampered tokens are rejected with HTTP 403 before the upgrade.

Path role is validated against the JWT role claim — patients cannot
subscribe to the "doctor" channel.
"""
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError

from app.core.security import decode_token
from app.core.ws_manager import manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSockets"])

ALLOWED_ROLES = {"doctor", "secretary", "admin", "patient"}


@router.websocket("/ws/alerts/{role}")
async def alerts_socket(
    websocket: WebSocket,
    role: str,
    token: str = Query(..., description="JWT access token"),
) -> None:
    if role not in ALLOWED_ROLES:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    token_role = payload.get("role")
    if token_role != role and token_role != "admin":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(role, websocket)
    try:
        while True:
            # Server is push-only; consume client pings/pongs and discard.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(role, websocket)
    except Exception as exc:  # pragma: no cover
        logger.warning("WS error for role=%s: %s", role, exc)
        await manager.disconnect(role, websocket)
