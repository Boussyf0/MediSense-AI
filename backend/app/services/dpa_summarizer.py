"""
DPA Summarizer service — US-41.

RESPONSIBILITY:
  Aggregate data from 3 sources into a single DPA summary payload:
    1. Chat messages  → patient symptoms (last 7 days)
    2. IoT anomalies  → biometric context (last 30 days)
    3. Agent output   → recommended actions (from orchestrator)

  Then persist the summary to `dpa_summaries` table and return it.

DATA FLOW:
  Doctor opens patient file
    → GET /doctor/patient/{uuid}/dpa-summary
      → dpa_summarizer.build(patient_id, db)
        → [1] fetch_recent_symptoms() from messages table
        → [2] fetch_iot_summary() from biometric_anomalies table
        → [3] generate_recommendations() via RAG pipeline (lightweight call)
        → create DPASummary row in DB
        → return DPASummaryOut schema

PERFORMANCE:
  We run sources [1] and [2] in parallel via asyncio.gather().
  Source [3] (recommendations) depends on [1] (symptoms) so it runs after.
  Target total latency: < 500ms P95 (acceptance criteria US-41).

SYMPTOM EXTRACTION:
  We decrypt the last 10 patient messages, extract symptom keywords,
  and de-duplicate them.  We do NOT re-run the full RAG pipeline — too slow.
  Instead we use the same medical_entities extractor from Sprint 3.

TREND DETECTION (IoT):
  We compute the trend from the last 3 anomalies of each metric:
    - All severity == 'critical' → 'critical'
    - Severity increasing → 'declining'
    - Severity decreasing → 'improving'
    - Otherwise → 'stable'
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.biometric_anomaly import BiometricAnomaly
from app.db.models.conversation import Conversation, Message
from app.db.models.dpa_summary import DPASummary, AgentAction
from app.rag.medical_entities import extract_entities
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYMPTOM_WINDOW_DAYS = 7
IOT_WINDOW_DAYS = 30
MAX_SYMPTOMS = 10


# ── Public API ────────────────────────────────────────────────────────────────

async def build(
    patient_id: str,
    db: AsyncSession,
    doctor_id: str | None = None,
) -> DPASummary:
    """
    Build and persist a DPA summary for a patient.

    Aggregates symptoms, IoT data, and recommendations in parallel.
    Stores result in dpa_summaries table and returns the ORM object.

    Args:
        patient_id : Patient UUID string.
        db         : Async DB session.
        doctor_id  : Doctor UUID (stored for audit; set on approval if None).

    Returns:
        DPASummary ORM instance (persisted, not yet committed).
    """
    patient_uuid = uuid.UUID(patient_id)

    # [1] + [2] in parallel — independent data sources
    symptoms_task = asyncio.create_task(_fetch_recent_symptoms(patient_uuid, db))
    iot_task = asyncio.create_task(_fetch_iot_summary(patient_uuid, db))

    symptoms, iot_data = await asyncio.gather(symptoms_task, iot_task)

    # [3] Recommendations depend on symptoms
    recommendations = _generate_recommendations(symptoms, iot_data)

    # Build payload
    payload: dict[str, Any] = {
        "patient_uuid": str(patient_uuid),
        "symptoms": symptoms,
        "iot_summary": iot_data,
        "recommended_actions": recommendations,
        "confidence": _compute_confidence(symptoms, iot_data),
        "data_freshness_minutes": 0,   # set by endpoint using created_at delta
    }

    # Persist
    summary = DPASummary(
        patient_id=patient_uuid,
        doctor_id=uuid.UUID(doctor_id) if doctor_id else None,
        status="PENDING",
        payload_before=payload,
        version=1,
    )
    db.add(summary)

    # Persist individual actions for per-action approval (US-42).
    # Attaching through the relationship lets SQLAlchemy's unit-of-work
    # populate summary_id after the summary's PK default fires on flush —
    # setting summary_id=summary.id manually here would write NULL because
    # the Column(default=uuid.uuid4) only runs at INSERT time.
    for action in recommendations:
        summary.actions.append(AgentAction(
            action_type=action.get("action", "unknown"),
            payload=action,
            status="pending",
        ))

    await db.flush()  # get summary.id without committing
    return summary


# ── Private helpers ───────────────────────────────────────────────────────────

async def _fetch_recent_symptoms(
    patient_id: uuid.UUID,
    db: AsyncSession,
) -> list[str]:
    """
    Extract symptom keywords from the patient's recent chat messages.

    Strategy:
      1. Find conversations for this patient (last 7 days).
      2. Decrypt up to 10 'user' role messages.
      3. Run medical entity extractor on each decrypted message.
      4. Collect unique symptom keywords.

    Why not re-run the full RAG pipeline?
      The DPA summary is built on-demand when a doctor opens a file.
      We need it in < 500ms.  The full pipeline with LLM would take 1-3s.
      Entity extraction (regex + ICD-10 lookup) takes ~5ms per message.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=SYMPTOM_WINDOW_DAYS)

        # Get recent conversations for this patient (last 7 days)
        conv_stmt = (
            select(Conversation)
            .where(
                Conversation.patient_id == patient_id,
                Conversation.created_at >= cutoff,
            )
            .order_by(desc(Conversation.created_at))
            .limit(3)
        )
        conv_result = await db.execute(conv_stmt)
        conversations = list(conv_result.scalars().all())

        # Fallback to historical conversations when no recent interaction exists.
        if not conversations:
            history_stmt = (
                select(Conversation)
                .where(Conversation.patient_id == patient_id)
                .order_by(desc(Conversation.created_at))
                .limit(3)
            )
            history_result = await db.execute(history_stmt)
            conversations = list(history_result.scalars().all())

        if not conversations:
            return []

        conv_ids = [c.id for c in conversations]

        # Get user messages (patient's actual words)
        msg_stmt = (
            select(Message)
            .where(
                Message.conversation_id.in_(conv_ids),
                Message.role == "user",
            )
            .order_by(desc(Message.created_at))
            .limit(10)
        )
        msg_result = await db.execute(msg_stmt)
        messages = list(msg_result.scalars().all())

        # Decrypt messages using pgcrypto
        symptoms: list[dict[str, str]] = []
        is_urgent = False
        
        for msg in messages:
            decrypted = await _decrypt_message(msg.id, db)  # type: ignore[arg-type]
            if decrypted:
                entities = extract_entities(decrypted)
                if entities.is_urgent:
                    is_urgent = True
                
                # 1. Use ICD-10 lookup first (already available via extract_entities)
                for symptom_name in entities.matched_symptoms:
                    symptoms.append({
                        "name": symptom_name,
                        "severity": "critical" if entities.is_urgent else "moderate",
                        "source": "icd10",
                    })

                # 2. Add symptom-like terms (drug names give context)
                if entities.drug_names:
                    for d in entities.drug_names[:2]:
                        symptoms.append({
                            "name": f"médicament: {d}",
                            "severity": "moderate",
                            "source": "chat",
                        })

                # 3. Extract free-text symptom phrases via restrictive regex + stoplist
                symptom_phrases = _extract_symptom_phrases(decrypted)
                symptoms.extend(symptom_phrases)

        # De-duplicate by name and cap
        seen: set[str] = set()
        unique_symptoms: list[dict[str, str]] = []
        for s in symptoms:
            s_name = s["name"].lower()
            if s_name not in seen:
                seen.add(s_name)
                unique_symptoms.append(s)
        return unique_symptoms[:MAX_SYMPTOMS], is_urgent

    except Exception as exc:
        logger.warning("dpa_symptoms_failed patient=%s err=%s", patient_id, exc)
        return [], False


async def _decrypt_message(message_id: uuid.UUID, db: AsyncSession) -> str | None:
    """Decrypt a message using pgcrypto (same pattern as chat.py)."""
    try:
        stmt = text(
            "SELECT pgp_sym_decrypt(content_encrypted, :key) "
            "FROM messages WHERE id = :id"
        )
        result = await db.execute(stmt, {
            "key": settings.PGCRYPTO_KEY,
            "id": str(message_id),
        })
        row = result.fetchone()
        return str(row[0]) if row and row[0] else None
    except Exception:
        logger.warning("pgcrypto decrypt failed for DPA message", exc_info=True)
        return None


async def _fetch_iot_summary(
    patient_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Fetch IoT anomalies and compute trend for the DPA summary.

    Returns the iot_summary dict matching the DPASummaryOut schema.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=IOT_WINDOW_DAYS)
        stmt = (
            select(BiometricAnomaly)
            .where(
                BiometricAnomaly.patient_id == patient_id,
                BiometricAnomaly.detected_at >= cutoff,
            )
            .order_by(desc(BiometricAnomaly.detected_at))
            .limit(10)
        )
        result = await db.execute(stmt)
        rows = list(result.scalars().all())

        if not rows:
            return {"latest_anomalies": [], "trend": "stable"}

        anomalies = [r.to_context_dict() for r in rows]
        trend = _compute_trend([r.severity for r in rows[:3]])  # type: ignore[arg-type]
        return {"latest_anomalies": anomalies[:5], "trend": trend}

    except Exception as exc:
        logger.warning("dpa_iot_failed patient=%s err=%s", patient_id, exc)
        return {"latest_anomalies": [], "trend": "stable"}


def _compute_trend(severities: list[str]) -> str:
    """
    Derive trend from the last 3 anomaly severities (newest-first).

    Critical → critical; increasing severity → declining; decreasing → improving.
    """
    if not severities:
        return "stable"
    sev_map = {"mild": 1, "moderate": 2, "critical": 3}
    levels = [sev_map.get(s, 0) for s in severities]
    if any(l == 3 for l in levels):
        return "critical"
    if len(levels) >= 2 and levels[0] > levels[-1]:
        return "declining"
    if len(levels) >= 2 and levels[0] < levels[-1]:
        return "improving"
    return "stable"


def _generate_recommendations(
    symptoms: list[str],
    iot_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Generate recommended actions from symptoms and IoT data.

    Sprint 4: Rule-based recommendations (fast, deterministic).
    Sprint 6: Replace with LLM-generated recommendations using RAG context.

    Returns a list of action dicts matching the RecommendedAction schema.
    """
    actions: list[dict[str, Any]] = []
    iot_trend = iot_data.get("trend", "stable")
    anomalies = iot_data.get("latest_anomalies", [])

    # Critical IoT → alert action
    if iot_trend == "critical":
        actions.append({
            "action": "alert",
            "message": "Anomalies biométriques critiques — consultation urgente requise",
            "urgency": "urgent",
        })

    # SpO2 anomaly → monitor
    spo2_anomalies = [a for a in anomalies if a.get("metric") == "SpO2"]
    if spo2_anomalies:
        actions.append({
            "action": "monitor",
            "metric": "SpO2",
            "frequency": "quotidien",
            "reasoning": f"SpO2={spo2_anomalies[0]['value']}% détecté",
        })

    # HR anomaly → monitor
    hr_anomalies = [a for a in anomalies if a.get("metric") == "HR"]
    if hr_anomalies:
        actions.append({
            "action": "monitor",
            "metric": "fréquence cardiaque",
            "frequency": "quotidien",
            "reasoning": f"FC={hr_anomalies[0]['value']}bpm détectée",
        })

    # Symptom-based recommendations
    symptom_text = " ".join(symptoms).lower()
    if "fièvre" in symptom_text or "temperature" in symptom_text:
        actions.append({
            "action": "refer",
            "specialist": "médecine générale",
            "urgency": "routine",
            "reasoning": "Fièvre signalée — évaluation médicale recommandée",
        })

    if "médicament:" in symptom_text:
        actions.append({
            "action": "prescribe",
            "reasoning": "Vérifier les médicaments en cours et interactions potentielles",
        })

    # Default: general follow-up if no specific action
    if not actions:
        actions.append({
            "action": "refer",
            "specialist": "médecine générale",
            "urgency": "routine",
            "reasoning": "Suivi médical de routine recommandé",
        })

    return actions


def _compute_confidence(symptoms: list[str], iot_data: dict[str, Any]) -> float:
    """
    Estimate confidence in the DPA summary quality.

    Higher confidence when we have both symptom data and IoT data.
    Lower confidence when we have little or no data.
    """
    score = 0.4   # base: we always have something
    if symptoms:
        score += min(len(symptoms) * 0.05, 0.3)   # up to +0.30 for 6+ symptoms
    if iot_data.get("latest_anomalies"):
        score += 0.2
    if iot_data.get("trend") != "stable":
        score += 0.1
    return min(score, 0.95)


import re as _re


_SYMPTOM_PATTERNS = [
    # Match: "j'ai mal à la tête depuis 5 minutes" -> name="tête", duration="5 minutes"
    r"(?:j'ai|j'avais|je ressens|je souffre de)\s+(?:mal\s+(?:à\s+la|au|aux)\s+|des\s+)?([a-zA-Zéèêëàâîïôùûüç\s]{3,20}?)(?:\s+depuis\s+(\d+\s*(?:minutes?|heures?|jours?|semaines?|mois)))?(?=$|\s+et|\s*\.)",
    
    # Match: "douleur intense au ventre depuis 2 jours" -> name="ventre", duration="2 jours"
    r"(?:douleurs?|fièvre|toux|essoufflement|fatigue|nausées?|vomissements?|vertiges?)\s+(?:intenses?\s+)?(?:au|à|dans\s+la|aux)\s+([a-zA-Zéèêëàâîïôùûüç\s]{3,20}?)(?:\s+depuis\s+(\d+\s*(?:minutes?|heures?|jours?|semaines?|mois)))?(?=$|\s+et|\s*\.)",
    
    # Match: "toux depuis 3 jours" -> name="toux", duration="3 jours"
    r"(douleurs?|fièvre|toux|essoufflement|fatigue|nausées?|vomissements?|vertiges?)(?:\s+depuis\s+(\d+\s*(?:minutes?|heures?|jours?|semaines?|mois)))?",
]
_SYMPTOM_RE = _re.compile("|".join(_SYMPTOM_PATTERNS), _re.IGNORECASE)

_STOPLIST = {"un", "une", "le", "la", "les", "des", "du", "au", "aux", "très", "beaucoup", "peu", "minutes", "heures", "jours", "depuis", "mal"}

def _extract_symptom_phrases(text: str) -> list[dict[str, str]]:
    """Extract symptom phrases from a patient message using restrictive regex and stoplist."""
    matches = _SYMPTOM_RE.findall(text)
    symptoms = []
    
    for m in matches:
        groups = [g for g in m if g]
        if not groups:
            continue
            
        name = groups[0].strip()
        duration = groups[1].strip() if len(groups) > 1 else None
        
        if len(name) < 3 or all(w in _STOPLIST for w in name.lower().split()):
            continue
            
        # Map generic "mal" to "douleur"
        if name.lower() == "mal":
            name = "douleur"
            
        symptom_dict = {
            "name": name[:60],
            "severity": "moderate",
            "source": "chat",
        }
        if duration:
            symptom_dict["duration"] = duration[:30]
        symptoms.append(symptom_dict)
            
    return symptoms[:5]
