"""
CRM Agent — Salesforce integration via webhook.

This module is a thin routing layer over app.services.salesforce_client.
All HTTP logic, circuit breaker state, and DB persistence live in salesforce_client.

RESPONSIBILITY:
  After triage and (optionally) booking, notify the CRM system so that:
    - URGENT cases: create a high-priority task for the on-call doctor/secretary.
    - ROUTINE cases: create a standard follow-up task linked to the appointment.
    - INFO cases: no CRM action (analytics only).

CIRCUIT BREAKER (owned by salesforce_client):
  State machine: CLOSED → OPEN → HALF-OPEN
    CLOSED: normal operation.
    OPEN: after FAILURE_THRESHOLD consecutive failures, reject requests for RESET_TIMEOUT_S.
    HALF-OPEN: after timeout, let one trial request through.
"""
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class CRMResult:
    """
    Output of the CRM agent.

    Attributes:
        sent           : True if webhook was successfully sent.
        skipped        : True if CRM is not configured or severity is INFO.
        cb_open        : True if circuit breaker blocked the request.
        status_code    : HTTP status from Salesforce (if sent).
        correlation_id : UUID4 tracing ID for this CRM event.
        message        : Human-readable result.
    """
    sent: bool
    skipped: bool = False
    cb_open: bool = False
    status_code: int | None = None
    correlation_id: str | None = None
    message: str = ""


async def run(
    patient_id: str,
    severity: str,
    appointment_id: str | None,
    specialist_type: str | None,
    query_fr: str,
    iot_triggered: bool = False,
    db: AsyncSession | None = None,
) -> CRMResult:
    """
    Send CRM webhook to Salesforce.

    Args:
        patient_id      : Patient UUID string.
        severity        : 'urgent' | 'routine' | 'info'.
        appointment_id  : UUID of created appointment (if any).
        specialist_type : Specialist type for the appointment.
        query_fr        : French-normalized patient query (truncated to 200 chars).
        iot_triggered   : Whether severity was escalated by IoT biometrics.
        db              : Optional async session for DB persistence.

    Returns:
        CRMResult. sent=False on any error — CRM failure is non-blocking.
    """
    from app.services.salesforce_client import send_crm_event

    sf_result = await send_crm_event(
        patient_id=patient_id,
        severity=severity,
        appointment_id=appointment_id,
        specialist_type=specialist_type,
        query_fr=query_fr,
        iot_triggered=iot_triggered,
        db=db,
    )

    return CRMResult(
        sent=sf_result.sent,
        skipped=sf_result.skipped,
        cb_open=sf_result.cb_open,
        status_code=sf_result.status_code,
        correlation_id=sf_result.correlation_id,
        message=sf_result.message,
    )
