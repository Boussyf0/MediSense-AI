"""
Salesforce CRM client — Sprint 6 US-24.

Responsibilities:
  1. Generate correlation_id (UUID4) per call for idempotent request tracing.
  2. Send HTTP POST to SALESFORCE_WEBHOOK_URL with enriched payload.
  3. Persist sync result to appointments.crm_sync_* columns via AsyncSession.
  4. Maintain circuit breaker state (CLOSED/OPEN/HALF-OPEN).

Design decisions:
  - Non-blocking: all DB writes use await db.flush() not commit.
  - Non-raising: all exceptions caught, logged, result returned.
  - Settings-driven: no os.getenv() calls — uses get_settings().
  - Correlation ID present in every payload and response for tracing.
  - CRM failures NEVER block the patient chat response.
"""
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Circuit breaker thresholds
FAILURE_THRESHOLD = 3
RESET_TIMEOUT_S = 60

# Process-local circuit breaker state.
#
# MULTI-WORKER LIMITATION: these variables are not shared across OS processes.
# In a Gunicorn/uvicorn deployment with --workers > 1, each worker maintains
# its own independent counter. Worker 1 can open the breaker while Workers 2-4
# still fire requests. For true distributed coordination, migrate these keys to
# Redis (e.g. INCRBY crm:cb:failures / SET crm:cb:open_since with EXPIRE 60).
# Tracked in backlog as a Sprint 7 improvement.
_cb_failures: int = 0
_cb_open_since: float | None = None


@dataclass
class SalesforceResult:
    sent: bool
    skipped: bool = False
    cb_open: bool = False
    status_code: int | None = None
    correlation_id: str | None = None
    message: str = ""


async def send_crm_event(
    patient_id: str,
    severity: str,
    appointment_id: str | None,
    specialist_type: str | None,
    query_fr: str,
    iot_triggered: bool = False,
    db: AsyncSession | None = None,
) -> SalesforceResult:
    """
    Send CRM webhook to Salesforce and persist the result.

    Args:
        patient_id      : Patient UUID string.
        severity        : 'urgent' | 'routine' | 'info'.
        appointment_id  : UUID of the linked appointment (if any).
        specialist_type : Specialist type for booking context.
        query_fr        : French-normalised patient query (truncated to 200 chars).
        iot_triggered   : Whether severity was escalated by IoT biometrics.
        db              : Optional async session for DB persistence.

    Returns:
        SalesforceResult — never raises.
    """
    global _cb_failures, _cb_open_since

    settings = get_settings()
    correlation_id = str(uuid.uuid4())

    if not settings.SALESFORCE_WEBHOOK_URL:
        logger.debug("salesforce_skipped: SALESFORCE_WEBHOOK_URL not configured")
        await _persist_sync_result(db, appointment_id, "SKIPPED", correlation_id, 0, None)
        return SalesforceResult(sent=False, skipped=True, correlation_id=correlation_id,
                                message="CRM non configuré")

    if severity == "info":
        await _persist_sync_result(db, appointment_id, "SKIPPED", correlation_id, 0, None)
        return SalesforceResult(sent=False, skipped=True, correlation_id=correlation_id,
                                message="INFO: pas d'action CRM")

    # Check circuit breaker
    if _cb_open_since is not None:
        elapsed = time.monotonic() - _cb_open_since
        if elapsed < RESET_TIMEOUT_S:
            await _persist_sync_result(db, appointment_id, "CB_OPEN", correlation_id, 0, "circuit breaker open")
            return SalesforceResult(
                sent=False, cb_open=True, correlation_id=correlation_id,
                message=f"Circuit breaker ouvert ({int(RESET_TIMEOUT_S - elapsed)}s restantes)",
            )
        # Half-open: let one request through
        _cb_open_since = None
        _cb_failures = 0

    payload = {
        "event_type": "appointment_triage",
        "correlation_id": correlation_id,
        "patient_id": patient_id,
        "appointment_id": appointment_id,
        "severity": severity,
        "specialist_type": specialist_type,
        "query_summary": query_fr[:200],
        "iot_triggered": iot_triggered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=settings.SALESFORCE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                settings.SALESFORCE_WEBHOOK_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Source": "MediSense-AI",
                    "X-Correlation-ID": correlation_id,
                    "Authorization": f"Bearer {settings.SALESFORCE_TOKEN}",
                },
            )

        if response.status_code >= 500:
            _cb_failures += 1
            if _cb_failures >= FAILURE_THRESHOLD:
                _cb_open_since = time.monotonic()
                logger.warning("salesforce_circuit_open after %d failures", _cb_failures)
            error_msg = f"Salesforce erreur HTTP {response.status_code}"
            await _persist_sync_result(db, appointment_id, "FAILED", correlation_id, 1, error_msg)
            return SalesforceResult(
                sent=False, status_code=response.status_code,
                correlation_id=correlation_id, message=error_msg,
            )

        # Success — reset circuit breaker failures
        _cb_failures = 0
        logger.info(
            "salesforce_sent patient=%s severity=%s status=%d correlation=%s",
            patient_id, severity, response.status_code, correlation_id,
        )
        await _persist_sync_result(db, appointment_id, "SENT", correlation_id, 0, None)
        return SalesforceResult(
            sent=True, status_code=response.status_code,
            correlation_id=correlation_id,
            message=f"CRM notifié (HTTP {response.status_code})",
        )

    except Exception as exc:
        _cb_failures += 1
        if _cb_failures >= FAILURE_THRESHOLD:
            _cb_open_since = time.monotonic()
        error_msg = f"Erreur réseau CRM: {exc}"
        logger.warning("salesforce_failed patient=%s err=%s", patient_id, exc)
        await _persist_sync_result(db, appointment_id, "FAILED", correlation_id, 1, error_msg)
        return SalesforceResult(sent=False, correlation_id=correlation_id, message=error_msg)


async def _persist_sync_result(
    db: AsyncSession | None,
    appointment_id: str | None,
    status: str,
    correlation_id: str,
    retry_count_delta: int,
    error: str | None,
) -> None:
    """Write CRM sync state to appointments table. Never raises."""
    if db is None or appointment_id is None:
        return
    try:
        from app.db.models.appointment import Appointment

        synced_at = datetime.now(timezone.utc) if status == "SENT" else None
        stmt = (
            update(Appointment)
            .where(Appointment.appointment_uuid == uuid.UUID(appointment_id))
            .values(
                crm_sync_status=status,
                crm_correlation_id=correlation_id,
                crm_retry_count=Appointment.crm_retry_count + retry_count_delta,
                crm_last_error=error,
                crm_synced_at=synced_at,
            )
        )
        await db.execute(stmt)
        await db.flush()
    except Exception as exc:
        logger.warning("salesforce_persist_failed appointment=%s err=%s", appointment_id, exc)
