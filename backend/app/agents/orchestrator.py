"""
Multi-Agent Orchestrator — Sprint 4, US-14.

STATE MACHINE:
  INIT → TRIAGE → BOOK       → CRM → COMPLETE
               → ESCALATE    → CRM → COMPLETE
               → INFO        →     → COMPLETE

DESIGN PRINCIPLES:

1. AGENT ISOLATION
   Each agent has its own timeout (5s).  An agent that hangs or crashes
   does NOT cascade to other agents.  This is achieved via asyncio.wait_for()
   around every agent call and try/except around each result.

2. CIRCUIT BREAKER AT AGENT LEVEL
   CRM agent has a module-level circuit breaker (see crm_agent.py).
   Booking agent catches all DB exceptions internally.
   Triage agent is pure CPU (regex) — no network, no circuit breaker needed.

3. CONVERSATION HISTORY CONTINUITY
   Agent state is keyed by conversation_id.  The Redis cache (US-15) allows
   the orchestrator to rebuild context if the patient returns within 24h.

4. ASYNCIO.TASKGROUP vs asyncio.gather
   We use asyncio.gather() here because:
   - TaskGroup (Python 3.11+) cancels ALL tasks if one raises — too aggressive
     for our fault-tolerant medical use case.
   - gather(return_exceptions=True) lets each agent fail independently.
   The booking and CRM agents run SEQUENTIALLY (CRM needs booking result),
   but triage runs FIRST (its output determines the flow).

5. TIMEOUT STRATEGY
   Each agent call: 5s timeout.
   Total orchestrator budget: 15s (triage + booking + CRM in series worst case).
   This is far below the 30s Nginx timeout, leaving room for the RAG pipeline
   that ran before the orchestrator.

INTEGRATION WITH RAG PIPELINE:
  The orchestrator is called AFTER the RAG pipeline completes.
  The chat endpoint (chat.py) calls:
    1. pipeline.run() → PipelineResult (the medical answer)
    2. orchestrator.run_agent_flow() → AgentResult (triage + booking + CRM)
  Both results are stored in the conversation history and returned to the UI.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.triage_agent import run as _triage_run, Severity, TriageResult
from app.agents.booking_agent import run as _booking_run, BookingResult
from app.agents.crm_agent import run as _crm_run, CRMResult

logger = logging.getLogger(__name__)

AGENT_TIMEOUT_S = 5.0


class AgentRoute(str, Enum):
    """Final route taken by the orchestrator."""
    ESCALATE = "escalate"   # urgent — SAMU 141
    BOOK = "book"           # routine — appointment scheduled
    INFO = "info"           # informational only


@dataclass
class AgentResult:
    """
    Complete output from the orchestrator.

    Attributes:
        route          : Which branch was taken.
        triage         : Full triage agent output.
        booking        : Booking agent output (None for ESCALATE/INFO).
        crm            : CRM agent output (None if skipped).
        chat_message   : Composed message to show the patient.
        timings_ms     : Per-agent timing for observability.
        errors         : Non-fatal errors (agent timeouts, partial failures).
    """
    route: AgentRoute
    triage: TriageResult
    booking: BookingResult | None = None
    crm: CRMResult | None = None
    chat_message: str = ""
    timings_ms: dict[str, float] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


async def run_agent_flow(
    query_fr: str,
    patient_id: str | None,
    conversation_id: str | None,
    iot_anomalies: list[dict[str, Any]] | None,
    is_urgent_from_rag: bool,
    db: AsyncSession | None,
) -> AgentResult:
    """
    Execute the full agent flow for a patient interaction.

    Args:
        query_fr            : French-normalized patient query.
        patient_id          : Patient UUID string (None for anonymous).
        conversation_id     : Conversation UUID (for history continuity).
        iot_anomalies       : Biometric anomalies from IoT context (US-13).
        is_urgent_from_rag  : Urgency flag from RAG safety pre-check.
        db                  : Async DB session (needed by booking agent).

    Returns:
        AgentResult with full route decision and composed chat message.
    """
    import time
    timings: dict[str, float] = {}
    errors: list[str] = []

    logger.info(
        "orchestrator_start conversation=%s patient=%s",
        conversation_id, patient_id,
    )

    # ── Step 1: Triage (always runs) ────────────────────────────────────────
    t0 = time.perf_counter()
    triage = await _run_with_timeout(
        _triage_run(
            query_fr=query_fr,
            iot_anomalies=iot_anomalies,
            is_urgent_from_rag=is_urgent_from_rag,
        ),
        name="triage",
        errors=errors,
        fallback=TriageResult(
            severity=Severity.INFO,
            reason="Triage timeout — fallback to INFO",
            confidence=0.0,
        ),
    )
    timings["triage"] = (time.perf_counter() - t0) * 1000

    # ── Step 2: Route based on severity ─────────────────────────────────────

    # URGENT → skip booking, alert immediately
    if triage.severity == Severity.URGENT:
        crm = await _run_crm(
            patient_id, "urgent", None, None, query_fr,
            triage.iot_triggered, errors, timings, db
        )
        msg = _compose_urgent_message(triage)
        return AgentResult(
            route=AgentRoute.ESCALATE,
            triage=triage,
            crm=crm,
            chat_message=msg,
            timings_ms=timings,
            errors=errors,
        )

    # ROUTINE → try to book
    if triage.severity == Severity.ROUTINE and patient_id and db:
        t0 = time.perf_counter()
        booking = await _run_with_timeout(
            _booking_run(
                patient_id=patient_id,
                specialist_type=triage.specialist,
                db=db,
            ),
            name="booking",
            errors=errors,
            fallback=BookingResult(
                success=False,
                message="Booking timeout. Contactez le secrétariat.",
            ),
        )
        timings["booking"] = (time.perf_counter() - t0) * 1000

        crm = await _run_crm(
            patient_id, "routine",
            booking.appointment_id, triage.specialist,
            query_fr, triage.iot_triggered, errors, timings, db
        )
        msg = _compose_routine_message(triage, booking)
        return AgentResult(
            route=AgentRoute.BOOK,
            triage=triage,
            booking=booking,
            crm=crm,
            chat_message=msg,
            timings_ms=timings,
            errors=errors,
        )

    # INFO (or no DB session for booking)
    crm = await _run_crm(
        patient_id, "info", None, None, query_fr,
        False, errors, timings, db
    )
    return AgentResult(
        route=AgentRoute.INFO,
        triage=triage,
        crm=crm,
        chat_message="",   # RAG pipeline reply is used as-is for INFO
        timings_ms=timings,
        errors=errors,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _run_with_timeout(coro: Any, name: str, errors: list[str], fallback: Any) -> Any:
    """
    Run a coroutine with AGENT_TIMEOUT_S timeout.

    On timeout or any exception → log, append to errors, return fallback.
    This ensures one broken agent never blocks the full orchestrator.
    """
    try:
        return await asyncio.wait_for(coro, timeout=AGENT_TIMEOUT_S)
    except asyncio.TimeoutError:
        msg = f"{name}_agent_timeout after {AGENT_TIMEOUT_S}s"
        logger.warning(msg)
        errors.append(msg)
        return fallback
    except Exception as exc:
        msg = f"{name}_agent_error: {exc}"
        logger.error(msg)
        errors.append(msg)
        return fallback


async def _run_crm(
    patient_id: str | None,
    severity: str,
    appointment_id: str | None,
    specialist_type: str | None,
    query_fr: str,
    iot_triggered: bool,
    errors: list[str],
    timings: dict[str, float],
    db: AsyncSession | None = None,
) -> CRMResult | None:
    """Run the CRM agent with timeout. Non-blocking."""
    if not patient_id:
        return None
    import time
    t0 = time.perf_counter()
    result = await _run_with_timeout(
        _crm_run(
            patient_id=patient_id,
            severity=severity,
            appointment_id=appointment_id,
            specialist_type=specialist_type,
            query_fr=query_fr,
            iot_triggered=iot_triggered,
            db=db,
        ),
        name="crm",
        errors=errors,
        fallback=CRMResult(sent=False, message="CRM timeout"),
    )
    timings["crm"] = (time.perf_counter() - t0) * 1000
    return result


def _compose_urgent_message(triage: TriageResult) -> str:
    """Compose the emergency message shown to the patient."""
    base = (
        "URGENCE MÉDICALE: Veuillez appeler immédiatement le 141 (SAMU Maroc) "
        "ou vous rendre aux urgences les plus proches."
    )
    if triage.iot_triggered:
        return (
            f"ALERTE: {triage.reason}. "
            f"Ces données biométriques nécessitent une prise en charge immédiate. "
            f"{base}"
        )
    return f"{triage.reason}. {base}"


def _compose_routine_message(triage: TriageResult, booking: BookingResult) -> str:
    """Compose the appointment confirmation message."""
    if booking.success:
        return (
            f"D'après votre description, une consultation en {booking.specialist_type} "
            f"est recommandée. {booking.message} "
            f"Vous recevrez une confirmation par SMS."
        )
    return (
        f"Une consultation en {triage.specialist or 'médecine générale'} est recommandée. "
        f"{booking.message}"
    )
