"""
Medical safety layer — guardrails beyond prompt engineering.

Three levels of protection:
  1. Confidence gate: if retrieval confidence is too low, refuse to answer
  2. Drug dosage warning: if response mentions dosages, inject mandatory disclaimer
  3. Urgency override: cardiac/respiratory/neuro symptoms → immediate SAMU alert

Why code-level safety instead of just prompt instructions?
  Prompt-only guardrails can be bypassed by adversarial inputs.
  Code-level checks are deterministic and cannot be prompt-injected.
"""
import re
from dataclasses import dataclass

from app.rag.medical_entities import ExtractedEntities

# Minimum average retrieval score to trust the response
CONFIDENCE_THRESHOLD = 0.3

# Patterns that indicate dosage information in LLM output
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


@dataclass
class SafetyResult:
    """Output of the safety check."""
    should_block: bool
    override_response: str | None
    disclaimers: list[str]
    is_urgent: bool
    confidence: float


def pre_generation_check(
    entities: ExtractedEntities,
    retrieval_scores: list[float],
) -> SafetyResult:
    """
    Run safety checks BEFORE LLM generation.

    Called after retrieval, before calling Mistral 7B.
    Can block generation entirely if confidence is too low or situation is urgent.
    """
    avg_score = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0.0
    disclaimers = [STANDARD_DISCLAIMER]

    # Urgency override — don't wait for LLM, respond immediately
    if entities.is_urgent:
        return SafetyResult(
            should_block=True,
            override_response=URGENCY_MESSAGE,
            disclaimers=[],
            is_urgent=True,
            confidence=avg_score,
        )

    # Low confidence — refuse to answer
    if avg_score < CONFIDENCE_THRESHOLD:
        return SafetyResult(
            should_block=True,
            override_response=LOW_CONFIDENCE_MESSAGE,
            disclaimers=[],
            is_urgent=False,
            confidence=avg_score,
        )

    # Drug mentioned — pre-add dosage disclaimer
    if entities.drug_names:
        disclaimers.append(DOSAGE_DISCLAIMER)

    return SafetyResult(
        should_block=False,
        override_response=None,
        disclaimers=disclaimers,
        is_urgent=False,
        confidence=avg_score,
    )


def post_generation_check(response_text: str, disclaimers: list[str]) -> str:
    """
    Run safety checks AFTER LLM generation.

    Scans the response for dosage patterns and injects warnings if needed.
    Appends all accumulated disclaimers.
    """
    # If the LLM output mentions dosages but we didn't catch it pre-gen
    if _DOSAGE_RE.search(response_text) and DOSAGE_DISCLAIMER not in disclaimers:
        disclaimers.append(DOSAGE_DISCLAIMER)

    # Append disclaimers
    full_response = response_text
    for disclaimer in disclaimers:
        if disclaimer not in full_response:
            full_response += disclaimer

    return full_response
