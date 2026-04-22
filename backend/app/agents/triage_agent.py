"""
Triage Agent — classifies patient symptom severity.

ROLE IN THE ORCHESTRATOR:
  The triage agent is always the FIRST agent to run after the router decides
  the intent is medical.  Its output (severity) determines which branch the
  orchestrator takes:
    - URGENT   → skip booking, emit SAMU alert, notify doctor on-call
    - ROUTINE  → proceed to booking_agent
    - INFO     → return informational response only

HOW IT WORKS:
  1. Check pre-computed IoT severity (critical biometrics = always URGENT).
  2. Apply regex patterns on the French-normalized query (fast, deterministic).
  3. Fall back to RAG safety layer urgency flag (already computed in pipeline).

WHY REGEX AND NOT LLM?
  Triage for emergency conditions MUST be deterministic.
  An LLM can hallucinate or be prompt-injected into downgrading severity.
  Code-level pattern matching is:
    - Unhackable by adversarial inputs.
    - ~0ms latency (vs 800ms+ for an LLM call).
    - Auditable: every pattern is explicit and testable.

  This is the same philosophy as the safety layer in Sprint 3.

SEVERITY LEVELS:
  URGENT   — call 141 immediately, never book an appointment
  ROUTINE  — schedule appointment with appropriate specialist
  INFO     — patient wants information, no appointment needed
"""
import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    URGENT = "urgent"
    ROUTINE = "routine"
    INFO = "info"


# ── Urgency patterns (same logic as safety.py but structured for agent output) ──

_URGENT_RE = re.compile(
    r"douleur\s+thoracique"
    r"|oppression\s+poitrine"
    r"|difficultés?\s+respir"
    r"|dyspnée"
    r"|essoufflement\s+soudain"
    r"|perte\s+de\s+connaissance"
    r"|évanouissement"
    r"|convulsion"
    r"|paralysie"
    r"|avc"
    r"|accident\s+vasculaire"
    r"|infarctus"
    r"|hémorragie"
    r"|saignement\s+abondant"
    r"|urgence",
    re.IGNORECASE,
)

_ROUTINE_RE = re.compile(
    r"rendez.?vous"
    r"|consultation"
    r"|voir\s+un?\s+médecin"
    r"|suivi"
    r"|renouvellement"
    r"|ordonnance"
    r"|bilan"
    r"|examen"
    r"|spécialiste"
    r"|fièvre\s+(depuis|de)\s+\d"   # fever lasting days = routine
    r"|douleur\s+(depuis|de)\s+\d"  # pain lasting days = routine
    r"|chronique",
    re.IGNORECASE,
)


@dataclass
class TriageResult:
    """
    Output of the triage agent.

    Attributes:
        severity         : URGENT | ROUTINE | INFO
        reason           : Human-readable explanation of the decision.
        specialist       : Suggested specialist type for ROUTINE cases.
        iot_triggered    : True if severity was escalated by IoT biometrics.
        confidence       : 0–1 confidence in the triage decision.
    """
    severity: Severity
    reason: str
    specialist: str | None = None
    iot_triggered: bool = False
    confidence: float = 1.0


async def run(
    query_fr: str,
    iot_anomalies: list[dict[str, Any]] | None = None,
    is_urgent_from_rag: bool = False,
) -> TriageResult:
    """
    Classify patient interaction severity.

    Args:
        query_fr            : French-normalized patient query.
        iot_anomalies       : Recent biometric anomalies (from IoTContext).
        is_urgent_from_rag  : Urgency flag from RAG safety pre-check.

    Returns:
        TriageResult with severity, reason, specialist hint.

    Timeout: caller wraps this in asyncio.wait_for(timeout=5s).
    This function is synchronous-fast (regex only) but declared async
    for uniformity with other agents that may do async DB/API calls.
    """
    anomalies = iot_anomalies or []

    # 1. IoT critical biometrics → immediate escalation
    critical = [a for a in anomalies if a.get("severity") == "critical"]
    if critical:
        metrics = ", ".join(f"{a['metric']}={a['value']}{a.get('unit','')}" for a in critical)
        return TriageResult(
            severity=Severity.URGENT,
            reason=f"Anomalie biométrique critique détectée: {metrics}",
            iot_triggered=True,
            confidence=1.0,
        )

    # 2. RAG safety urgency flag (cardiac/neuro keywords)
    if is_urgent_from_rag or _URGENT_RE.search(query_fr):
        return TriageResult(
            severity=Severity.URGENT,
            reason="Symptômes d'urgence détectés dans la requête",
            confidence=1.0,
        )

    # 3. Routine: appointment-seeking language
    if _ROUTINE_RE.search(query_fr):
        specialist = _suggest_specialist(query_fr)
        return TriageResult(
            severity=Severity.ROUTINE,
            reason="Patient demande une consultation ou un suivi",
            specialist=specialist,
            confidence=0.9,
        )

    # 4. Default: informational
    return TriageResult(
        severity=Severity.INFO,
        reason="Demande d'information médicale générale",
        confidence=0.8,
    )


def _suggest_specialist(query_fr: str) -> str | None:
    """
    Heuristic: map query keywords to a specialist type.

    This is intentionally simple for Sprint 4.
    Sprint 6 will replace this with a proper specialty classifier.
    """
    mapping = {
        r"cardi|cœur|cardiaque": "cardiologie",
        r"dermato|peau|acné|psoriasis": "dermatologie",
        r"ophtalmo|vision|yeux": "ophtalmologie",
        r"gynéco|grossesse|règles": "gynécologie",
        r"pédiatr|enfant|nourrisson": "pédiatrie",
        r"ortho|genou|hanche|colonne": "orthopédie",
        r"neuro|migraine|céphalée|épilepsie": "neurologie",
        r"endocrino|diabète|thyroïde": "endocrinologie",
        r"pneumo|poumons|asthme|bronchite": "pneumologie",
        r"gastro|intestin|colon|foie": "gastroentérologie",
    }
    for pattern, specialty in mapping.items():
        if re.search(pattern, query_fr, re.IGNORECASE):
            return specialty
    return "médecine générale"
