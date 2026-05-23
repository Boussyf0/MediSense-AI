"""Firebase Cloud Messaging service — Sprint 7 (US-29).

Sends push notifications to mobile clients on critical anomalies and other
patient-facing events. Initialised lazily from `FCM_SERVICE_ACCOUNT_B64` so
the backend stays bootable in dev/CI/cloud-demo environments without a
service-account JSON.

Mock mode (no credentials): payloads are logged and `send_to_token` returns
True. Real mode initialises a single global Firebase app and uses
`messaging.send`.

The service must never raise into the caller — the anomaly detector calls
this from inside the ingestion hot-path and a failed push must not block
data persistence.
"""
import base64
import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_initialised: bool = False
_mock_mode: bool = True


def _init_firebase() -> None:  # pragma: no cover - exercised only with real creds
    """Initialise the firebase_admin app exactly once. Falls back to mock mode
    if creds are missing or firebase-admin is not installed."""
    global _initialised, _mock_mode
    if _initialised:
        return
    _initialised = True

    raw_b64 = get_settings().FCM_SERVICE_ACCOUNT_B64
    if not raw_b64:
        logger.info("FCM running in MOCK mode (FCM_SERVICE_ACCOUNT_B64 unset)")
        _mock_mode = True
        return

    try:
        import firebase_admin
        from firebase_admin import credentials

        cred_dict = json.loads(base64.b64decode(raw_b64))
        cred = credentials.Certificate(cred_dict)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        _mock_mode = False
        logger.info("FCM initialised with service-account credentials")
    except Exception as exc:
        logger.warning("FCM init failed — falling back to MOCK mode: %s", exc)
        _mock_mode = True


async def send_to_token(token: str, title: str, body: str, data: dict[str, Any] | None = None) -> bool:
    """Send a push notification to a single device token.

    Returns True on success (or mock-mode log), False on transport failure.
    Caller-side errors propagate as False — never raises.
    """
    _init_firebase()

    if _mock_mode:
        logger.info(
            "FCM[mock] → %s… : %s / %s | data=%s",
            token[:12], title, body, data or {},
        )
        try:
            from app.api.v1.endpoints.metrics import fcm_sends_total
            fcm_sends_total.labels(outcome="mock").inc()
        except Exception:
            pass
        return True

    try:  # pragma: no cover - real network path
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
        )
        msg_id = messaging.send(message)
        logger.debug("FCM sent id=%s", msg_id)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("FCM send failed for token=%s…: %s", token[:12], exc)
        return False


async def send_to_tokens(tokens: list[str], title: str, body: str, data: dict[str, Any] | None = None) -> int:
    """Fan-out helper. Returns count of successful deliveries."""
    if not tokens:
        return 0
    sent = 0
    for tok in tokens:
        if await send_to_token(tok, title, body, data):
            sent += 1
    return sent


def reset_for_tests() -> None:
    """Clear cached init state — used by unit tests that toggle creds."""
    global _initialised, _mock_mode
    _initialised = False
    _mock_mode = True
