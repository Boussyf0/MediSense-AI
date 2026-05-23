"""
Medical safety layer — guardrails beyond prompt engineering.

Four levels of protection:
  1. Urgency override: cardiac/respiratory/neuro symptoms → immediate SAMU alert
  2. Adversarial query gate: injection / bypass / self-med attempts → pre-LLM block
  3. Confidence gate: if retrieval confidence is too low, refuse to answer
  4. Post-generation: dosage warnings, allergy alerts, standard disclaimers

Why code-level safety instead of just prompt instructions?
  Prompt-only guardrails can be bypassed by adversarial inputs.
  Code-level checks are deterministic and cannot be prompt-injected.
"""
import re
from dataclasses import dataclass

from app.rag.medical_entities import ExtractedEntities

# Minimum average retrieval score to trust the response.
# Below this, we still call the LLM but it must default to general guidance
# + "consult a professional" disclaimer (enforced by the system prompt).
# Set low so ordinary questions ("fatigue", "doliprane") reach the LLM.
CONFIDENCE_THRESHOLD = 0.1

# ── Adversarial query patterns (checked against the raw query, before LLM) ──

# Dosage bypass: explicit attempts to get dosages while bypassing safety guards
_DOSAGE_ADVERSARIAL_RE = re.compile(
    r"sans\s+disclaimer"
    r"|sans\s+mentionner"
    r"|ignore\s+.{0,30}consigne"
    r"|posologie\s+exacte"
    r"|dose\s+maximale"
    r"|dosage\s+agressif"
    r"|sans\s+consulter"
    r"|sans\s+avis\s+m[eé]dic"
    r"|sans\s+m[eé]decin"
    r"|sans\s+risque",
    re.IGNORECASE,
)

# Prompt injection: attempts to override system role or force hallucination
_INJECTION_RE = re.compile(
    r"r[eé]v[eè]le\s+.{0,30}instruction"
    r"|instructions?\s+interne"
    r"|contourne\s+.{0,30}r[eè]gle"
    r"|ignore\s+.{0,30}r[eè]gle"
    r"|ignore\s+.{0,30}contexte"
    r"|r[oô]le\s+d[eé]veloppeur"
    r"|mode\s+d[eé]veloppeur"
    r"|invente\s+.{0,30}r[eé]ponse"
    r"|sans\s+source\s+fiable"
    r"|n.{0,5}as\s+pas\s+de\s+source\s+fiable",
    re.IGNORECASE,
)

# Dangerous self-medication
_SELF_MED_RE = re.compile(
    r"autom[eé]dication"
    r"|auto-m[eé]dication"
    r"|(protocole|traitement).{0,40}sans\s+consulter",
    re.IGNORECASE,
)

# ── Patterns that indicate dosage information in LLM output ──────────────────
_DOSAGE_PATTERNS = [
    r"\d+\s*mg",
    r"\d+\s*ml",
    r"\d+\s*comprime",
    r"\d+\s*gelule",
    r"\d+\s*goutte",
    r"\d+\s*fois\s*par\s*jour",
    r"posologie",
    r"dosage",
]
_DOSAGE_RE = re.compile("|".join(_DOSAGE_PATTERNS), re.IGNORECASE)

# ── Static response strings ───────────────────────────────────────────────────

URGENCY_MESSAGE = (
    "URGENCE: Les symptomes decrits necessitent une prise en charge immediate. "
    "Appelez le 141 (SAMU Maroc) ou le 15 (urgences) immediatement. "
    "Ne prenez aucun medicament sans avis medical dans cette situation."
)

LOW_CONFIDENCE_MESSAGE = (
    "Je ne dispose pas d'informations suffisamment fiables pour repondre "
    "a cette question. Veuillez consulter votre medecin traitant ou appeler "
    "le 141 (SAMU Maroc) en cas d'urgence."
)

DOSAGE_DISCLAIMER = (
    "\n\nATTENTION: Les dosages mentionnes sont purement indicatifs. "
    "Respectez strictement la prescription de votre medecin. "
    "Ne modifiez jamais un traitement sans avis medical."
)

STANDARD_DISCLAIMER = (
    "\n\nCeci est une aide informative et non un diagnostic medical. "
    "Consultez un professionnel de sante."
)

DOSAGE_ADVERSARIAL_RESPONSE = (
    "Je ne peux pas fournir de posologie ou de dosage specifique en dehors "
    "d'un cadre medical supervise. Consultez votre medecin ou pharmacien."
    + DOSAGE_DISCLAIMER
)


@dataclass
class SafetyResult:
    """Output of the safety check."""
    should_block: bool
    override_response: str | None
    disclaimers: list[str]
    is_urgent: bool
    confidence: float


def check_allergy_conflict(
    response_text: str,
    patient_allergies: list[str],
) -> str | None:
    """
    Check if the response mentions a drug the patient is allergic to.

    Returns a warning string if a conflict is detected, else None.
    Called in post_generation_check when the patient profile has allergies.
    """
    if not patient_allergies:
        return None
    response_lower = response_text.lower()
    conflicts = [a for a in patient_allergies if a.lower() in response_lower]
    if conflicts:
        names = ", ".join(conflicts)
        return (
            f"\n\nALERTE ALLERGIE: Ce message mentionne {names}, "
            f"pour lesquels vous avez une allergie déclarée. "
            f"Consultez impérativement votre médecin avant toute prise."
        )
    return None


def pre_generation_check(
    entities: ExtractedEntities,
    retrieval_scores: list[float],
    query_text: str = "",
) -> SafetyResult:
    """
    Run safety checks BEFORE LLM generation.

    Order of precedence (highest → lowest):
      1. Urgency override (cardiac/neuro/respiratory emergency)
      2. Prompt injection / forced hallucination attempt
      3. Dangerous self-medication attempt
      4. Adversarial dosage bypass (drug detected + bypass language)
      5. Low retrieval confidence gate
      6. Normal path — drug mentioned → pre-add dosage disclaimer

    Args:
        entities:         Extracted medical entities (drugs, ICD-10, urgency flag).
        retrieval_scores: RRF scores from Qdrant hybrid search.
        query_text:       Raw (French-normalised) query — used for pattern matching.
    """
    avg_score = (
        sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0.0
    )
    disclaimers = [STANDARD_DISCLAIMER]

    # 1. Urgency override — respond immediately, no LLM
    if entities.is_urgent:
        return SafetyResult(
            should_block=True,
            override_response=URGENCY_MESSAGE,
            disclaimers=[],
            is_urgent=True,
            confidence=avg_score,
        )

    # 2. Prompt injection / forced hallucination — no LLM
    if _INJECTION_RE.search(query_text):
        # If a drug is also mentioned, caller expects dosage_disclaimer semantics
        if entities.drug_names:
            return SafetyResult(
                should_block=True,
                override_response=DOSAGE_ADVERSARIAL_RESPONSE,
                disclaimers=[],
                is_urgent=False,
                confidence=avg_score,
            )
        return SafetyResult(
            should_block=True,
            override_response=LOW_CONFIDENCE_MESSAGE,
            disclaimers=[],
            is_urgent=False,
            confidence=avg_score,
        )

    # 3. Dangerous self-medication attempt — no LLM
    if _SELF_MED_RE.search(query_text):
        return SafetyResult(
            should_block=True,
            override_response=LOW_CONFIDENCE_MESSAGE,
            disclaimers=[],
            is_urgent=False,
            confidence=avg_score,
        )

    # 4. Adversarial dosage bypass with known drug — no LLM
    if entities.drug_names and _DOSAGE_ADVERSARIAL_RE.search(query_text):
        return SafetyResult(
            should_block=True,
            override_response=DOSAGE_ADVERSARIAL_RESPONSE,
            disclaimers=[],
            is_urgent=False,
            confidence=avg_score,
        )

    # 5. Low confidence — refuse to answer
    if avg_score < CONFIDENCE_THRESHOLD:
        return SafetyResult(
            should_block=True,
            override_response=LOW_CONFIDENCE_MESSAGE,
            disclaimers=[],
            is_urgent=False,
            confidence=avg_score,
        )

    # 6. Normal path — dosage disclaimer is appended post-hoc only if the
    # LLM output actually mentions a dosage (handled by post_generation_check).
    # Pre-adding it caused refusal answers to ship with a misleading dosage warning.

    return SafetyResult(
        should_block=False,
        override_response=None,
        disclaimers=disclaimers,
        is_urgent=False,
        confidence=avg_score,
    )


def post_generation_check(
    response_text: str,
    disclaimers: list[str],
    patient_allergies: list[str] | None = None,
) -> str:
    """
    Run safety checks AFTER LLM generation.

    - Scans for dosage patterns and injects warnings if needed.
    - Checks for allergy conflicts if patient_allergies is provided.
    - Appends all accumulated disclaimers.
    """
    # If the LLM output mentions dosages but we didn't catch it pre-gen
    if _DOSAGE_RE.search(response_text) and DOSAGE_DISCLAIMER not in disclaimers:
        disclaimers.append(DOSAGE_DISCLAIMER)

    # Allergy conflict check
    if patient_allergies:
        allergy_warning = check_allergy_conflict(response_text, patient_allergies)
        if allergy_warning and allergy_warning not in disclaimers:
            disclaimers.append(allergy_warning)

    # Append disclaimers
    full_response = response_text
    for disclaimer in disclaimers:
        if disclaimer not in full_response:
            full_response += disclaimer

    return full_response
