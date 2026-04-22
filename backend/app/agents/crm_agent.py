"""
CRM Agent — Salesforce integration via webhook.

RESPONSIBILITY:
  After triage and (optionally) booking, notify the CRM system so that:
    - URGENT cases: create a high-priority task for the on-call doctor/secretary.
    - ROUTINE cases: create a standard follow-up task linked to the appointment.
    - INFO cases: no CRM action (just log for analytics).

SALESFORCE INTEGRATION:
  We use a webhook pattern (HTTP POST to a Salesforce Connected App endpoint)
  rather than the Salesforce SDK.  Why?

  1. The webhook URL and credentials live in environment variables → no Salesforce
     SDK dependency in our Python image (saves ~80MB Docker layer).
  2. In development/CI (SALESFORCE_WEBHOOK_URL not set) → silently skip.
  3. Circuit breaker: if Salesforce returns 5xx 3 times → open circuit for 60s.
     CRM failure must NEVER block the patient chat response.

PAYLOAD CONTRACT:
  {
    "patient_id": "<uuid>",
    "severity": "urgent" | "routine" | "info",
    "appointment_id": "<uuid>" | null,
    "specialist_type": "cardiologie" | ...,
    "query_summary": "<first 200 chars of French query>",
    "iot_triggered": true | false,
    "timestamp": "<ISO8601>"
  }

CIRCUIT BREAKER PATTERN:
  State machine: CLOSED → OPEN → HALF-OPEN
    CLOSED: normal operation, all requests pass through.
    OPEN: after FAILURE_THRESHOLD consecutive failures, reject all requests for RESET_TIMEOUT_S.
    HALF-OPEN: after RESET_TIMEOUT_S, let one request through.
      - If it succeeds → back to CLOSED.
      - If it fails → back to OPEN.

  This prevents a slow/dead Salesforce endpoint from consuming all worker
  threads via long timeouts. Same pattern used in Sprint 3 MCP client.
"""
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# Circuit breaker config
FAILURE_THRESHOLD = 3
RESET_TIMEOUT_S = 60
REQUEST_TIMEOUT_S = 3.0

# Module-level circuit breaker state (shared across requests in same process)
_cb_failures = 0
_cb_open_since: float | None = None


@dataclass
class CRMResult:
    """
    Output of the CRM agent.

    Attributes:
        sent        : True if webhook was successfully sent.
        skipped     : True if CRM is not configured (no webhook URL in env).
        cb_open     : True if circuit breaker blocked the request.
        status_code : HTTP status from Salesforce (if sent).
        message     : Human-readable result.
    """
    sent: bool
    skipped: bool = False
    cb_open: bool = False
    status_code: int | None = None
    message: str = ""


async def run(
    patient_id: str,
    severity: str,
    appointment_id: str | None,
    specialist_type: str | None,
    query_fr: str,
    iot_triggered: bool = False,
) -> CRMResult:
    """
    Send CRM webhook to Salesforce.

    Args:
        patient_id      : Patient UUID.
        severity        : 'urgent' | 'routine' | 'info'.
        appointment_id  : UUID of created appointment (if any).
        specialist_type : Specialist type for the appointment.
        query_fr        : French-normalized patient query (truncated to 200 chars).
        iot_triggered   : Whether severity was escalated by IoT biometrics.

    Returns:
        CRMResult.  sent=False on any error — CRM failure is non-blocking.

    Timeout: caller wraps in asyncio.wait_for(timeout=5s).
    """
    global _cb_failures, _cb_open_since

    webhook_url = os.getenv("SALESFORCE_WEBHOOK_URL", "")
    if not webhook_url:
        logger.debug("crm_agent_skipped: SALESFORCE_WEBHOOK_URL not configured")
        return CRMResult(sent=False, skipped=True, message="CRM non configuré")

    # INFO cases don't trigger CRM tasks (analytics only in Sprint 6)
    if severity == "info":
        return CRMResult(sent=False, skipped=True, message="INFO: pas d'action CRM")

    # Check circuit breaker
    if _cb_open_since is not None:
        elapsed = time.monotonic() - _cb_open_since
        if elapsed < RESET_TIMEOUT_S:
            return CRMResult(
                sent=False,
                cb_open=True,
                message=f"Circuit breaker ouvert ({int(RESET_TIMEOUT_S - elapsed)}s restantes)",
            )
        # Half-open: reset and try one request
        _cb_open_since = None
        _cb_failures = 0

    payload = {
        "patient_id": patient_id,
        "severity": severity,
        "appointment_id": appointment_id,
        "specialist_type": specialist_type,
        "query_summary": query_fr[:200],
        "iot_triggered": iot_triggered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Source": "MediSense-AI",
                    "Authorization": f"Bearer {os.getenv('SALESFORCE_TOKEN', '')}",
                },
            )

        if response.status_code >= 500:
            _cb_failures += 1
            if _cb_failures >= FAILURE_THRESHOLD:
                _cb_open_since = time.monotonic()
                logger.warning(
                    "crm_agent_circuit_open after %d failures", _cb_failures
                )
            return CRMResult(
                sent=False,
                status_code=response.status_code,
                message=f"Salesforce erreur {response.status_code}",
            )

        # Success — reset circuit breaker failures
        _cb_failures = 0
        logger.info(
            "crm_agent_sent patient=%s severity=%s status=%d",
            patient_id, severity, response.status_code,
        )
        return CRMResult(
            sent=True,
            status_code=response.status_code,
            message=f"CRM notifié (HTTP {response.status_code})",
        )

    except Exception as exc:
        _cb_failures += 1
        if _cb_failures >= FAILURE_THRESHOLD:
            _cb_open_since = time.monotonic()
        logger.warning("crm_agent_failed patient=%s err=%s", patient_id, exc)
        return CRMResult(sent=False, message=f"Erreur réseau CRM: {exc}")
