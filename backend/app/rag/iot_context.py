"""
US-13 — IoT context fetcher for the RAG pipeline.

ROLE IN THE PIPELINE:
  Inserted as Step 0 (before language detection) in pipeline.run() and
  pipeline.run_stream().  The anomaly context is passed down to the LLM
  as additional context alongside Qdrant RAG chunks.

WHY STEP 0?
  We want the language normalizer (step 2) to have the full patient
  context available.  More importantly, the safety pre-check (step 5)
  must be able to escalate CRITICAL anomalies independently of what
  the patient asked — e.g., SpO2 = 88% is an emergency regardless of
  whether the patient asked "pourquoi j'ai sommeil?".

QUERY STRATEGY:
  We fetch the last 5 anomalies from the past 30 days, ordered newest-first.
  Why 5?
    - Enough to detect a trend (e.g., 3 consecutive SpO2 drops).
    - Small enough to fit in the LLM context window without crowding out RAG.
  Why 30 days?
    - Clinically relevant window (chronic condition monitoring).
    - Balances recency with completeness.

GRACEFUL DEGRADATION:
  If TimescaleDB/PostgreSQL is unreachable, or the patient has no anomalies,
  we return an empty IoTContext. The pipeline continues normally.
  This is critical: a DB timeout must NEVER block a patient from getting
  a response — especially in an emergency scenario.

MOCK DATA FOR DEVELOPMENT:
  When MOCK_IOT=true in env, we return a set of sample anomalies.
  This lets the team develop and demo Sprint 4 features without a running
  IoT sensor infrastructure (which is Sprint 7).
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.biometric_anomaly import BiometricAnomaly

logger = logging.getLogger(__name__)

# Number of recent anomalies to include in chat context
ANOMALY_WINDOW_DAYS = 30
ANOMALY_LIMIT = 5

# Severity that triggers a safety override (same escalation as urgency keywords)
CRITICAL_SEVERITY = "critical"


@dataclass
class IoTContext:
    """
    Container for IoT anomalies injected into the RAG pipeline.

    Attributes:
        anomalies      : List of serialized anomaly dicts (newest-first).
        has_critical   : True if any anomaly has severity == 'critical'.
        summary_text   : Human-readable summary injected into LLM prompt.
    """
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    has_critical: bool = False
    summary_text: str = ""

    @property
    def is_empty(self) -> bool:
        return len(self.anomalies) == 0


def _build_summary_text(anomalies: list[dict[str, Any]]) -> str:
    """
    Convert anomaly list into a concise paragraph the LLM can read.

    Example output:
      "Données IoT récentes (30 derniers jours): SpO2=92% (seuil 95%, critique,
       détecté 2026-05-20); HR=105bpm (seuil 100bpm, modéré, détecté 2026-05-19)"
    """
    if not anomalies:
        return ""
    parts = []
    for a in anomalies:
        detected = a.get("detected_at", "")[:10] if a.get("detected_at") else "?"
        parts.append(
            f"{a['metric']}={a['value']}{a.get('unit', '')} "
            f"(seuil {a['threshold']}{a.get('unit', '')}, "
            f"{a['severity']}, détecté {detected})"
        )
    return "Données IoT récentes (30 derniers jours): " + "; ".join(parts)


async def fetch_iot_context(
    patient_id: str | None,
    db: AsyncSession | None,
) -> IoTContext:
    """
    Fetch recent biometric anomalies for a patient.

    Args:
        patient_id : Patient UUID string.  None → return empty context.
        db         : Async SQLAlchemy session.  None → fall back to mock or empty.

    Returns:
        IoTContext with anomalies, has_critical flag, and summary_text.
    """
    if not patient_id:
        return IoTContext()

    # Development/demo mode — return mock data without hitting the DB
    if os.getenv("MOCK_IOT", "false").lower() == "true":
        return _mock_iot_context(patient_id)

    if db is None:
        return IoTContext()

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=ANOMALY_WINDOW_DAYS)
        patient_uuid = uuid.UUID(patient_id)

        stmt = (
            select(BiometricAnomaly)
            .where(
                BiometricAnomaly.patient_id == patient_uuid,
                BiometricAnomaly.detected_at >= cutoff,
            )
            .order_by(desc(BiometricAnomaly.detected_at))
            .limit(ANOMALY_LIMIT)
        )
        result = await db.execute(stmt)
        rows: list[BiometricAnomaly] = list(result.scalars().all())

        if not rows:
            return IoTContext()

        anomalies = [r.to_context_dict() for r in rows]
        has_critical = any(a["severity"] == CRITICAL_SEVERITY for a in anomalies)
        return IoTContext(
            anomalies=anomalies,
            has_critical=has_critical,
            summary_text=_build_summary_text(anomalies),
        )

    except Exception as exc:
        # Graceful degradation — IoT failure must not block the chat
        logger.warning("iot_context_fetch_failed patient=%s err=%s", patient_id, exc)
        return IoTContext()


def _mock_iot_context(patient_id: str) -> IoTContext:  # pragma: no cover  # noqa: ARG001
    """
    Return realistic mock anomalies for development and demo.

    These values represent a patient with mild hypoxemia and tachycardia,
    which is a common clinical scenario relevant to the RAG chatbot testing.
    """
    now = datetime.now(timezone.utc)
    anomalies = [
        {
            "metric": "SpO2",
            "value": 92.0,
            "unit": "%",
            "threshold": 95.0,
            "severity": "critical",
            "source": "oximeter_mock",
            "detected_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "metric": "HR",
            "value": 105.0,
            "unit": "bpm",
            "threshold": 100.0,
            "severity": "moderate",
            "source": "smartwatch_mock",
            "detected_at": (now - timedelta(hours=6)).isoformat(),
        },
    ]
    return IoTContext(
        anomalies=anomalies,
        has_critical=True,
        summary_text=_build_summary_text(anomalies),
    )
