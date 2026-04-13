"""
RAG Pipeline Orchestrator — full execution path.

Steps:
  [1] Language detection (langdetect + Darija stopwords)
  [2] Query normalization (Darija/AR → clinical French via Mistral)
  [3] Parallel retrieval:
      [3a] Qdrant dense + BM25 hybrid (RRF)
      [3b] MCP servers (ANSM + ICD-11) with circuit breaker
  [4] Medical entity extraction + ICD-10 payload boost
  [5] Safety pre-check (confidence gate, urgency detection)
  [6] LLM generation (Mistral 7B, streaming or blocking)
  [7] Safety post-check (dosage warnings, disclaimers)
"""
import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Any

from app.rag.language import detect_language
from app.rag.normalizer import normalize_to_french
from app.rag.medical_entities import extract_entities
from app.rag.vectorstore import hybrid_search
from app.rag.safety import pre_generation_check, post_generation_check
from app.rag.llm import generate, generate_stream
from app.mcp.client import fetch_mcp_context


@dataclass
class PipelineResult:
    """Full result from the RAG pipeline (non-streaming mode)."""
    reply: str
    sources: list[dict[str, Any]]
    language: str
    confidence: float
    is_urgent: bool
    mcp_data: dict[str, Any]
    query_fr: str  # normalized French query (for audit/debug)


async def run(
    user_message: str,
    patient_allergies: list[str] | None = None,
) -> PipelineResult:
    """
    Execute the full RAG pipeline (non-streaming).

    Args:
        user_message: Raw patient message in any supported language.
        patient_allergies: Optional list of known patient allergies (from profile).

    Returns:
        PipelineResult with reply, sources, confidence, etc.
    """
    # [1] Language detection
    detected_lang = detect_language(user_message)

    # [2] Normalize to French
    query_fr = await normalize_to_french(user_message, detected_lang)

    # [4] Extract medical entities (from French query)
    entities = extract_entities(query_fr)

    # [3] Parallel: Qdrant retrieval + MCP fetch
    qdrant_task = asyncio.create_task(
        _safe_hybrid_search(query_fr, entities.icd10_codes)
    )
    mcp_task = asyncio.create_task(
        fetch_mcp_context(
            query_fr,
            drug_name=entities.drug_names[0] if entities.drug_names else None,
        )
    )

    chunks, mcp_data = await asyncio.gather(qdrant_task, mcp_task)

    # [5] Safety pre-check
    scores = [c.get("score", 0.0) for c in chunks]
    safety = pre_generation_check(entities, scores)

    if safety.should_block:
        return PipelineResult(
            reply=safety.override_response or "",
            sources=[],
            language=detected_lang,
            confidence=safety.confidence,
            is_urgent=safety.is_urgent,
            mcp_data=mcp_data,
            query_fr=query_fr,
        )

    # [6] LLM generation
    raw_reply = await generate(
        user_message=user_message,
        context_chunks=chunks,
        mcp_data=mcp_data,
        response_lang=detected_lang,
    )

    # [7] Safety post-check
    reply = post_generation_check(raw_reply, safety.disclaimers)

    # Format sources for response
    sources = [
        {
            "source": c.get("source", ""),
            "type": c.get("type", ""),
            "name": c.get("name", ""),
            "score": c.get("score", 0.0),
        }
        for c in chunks
    ]

    return PipelineResult(
        reply=reply,
        sources=sources,
        language=detected_lang,
        confidence=safety.confidence,
        is_urgent=False,
        mcp_data=mcp_data,
        query_fr=query_fr,
    )


async def run_stream(
    user_message: str,
    patient_allergies: list[str] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Execute the RAG pipeline with SSE streaming.

    Yields event dicts suitable for Server-Sent Events:
      {"type": "lang",    "value": "darija"}
      {"type": "sources", "value": [{...}]}
      {"type": "token",   "value": "Selon"}
      {"type": "done",    "confidence": 0.82}
    """
    # [1] Language detection
    detected_lang = detect_language(user_message)
    yield {"type": "lang", "value": detected_lang}

    # [2] Normalize to French
    query_fr = await normalize_to_french(user_message, detected_lang)

    # [4] Extract medical entities
    entities = extract_entities(query_fr)

    # [3] Parallel retrieval
    qdrant_task = asyncio.create_task(
        _safe_hybrid_search(query_fr, entities.icd10_codes)
    )
    mcp_task = asyncio.create_task(
        fetch_mcp_context(
            query_fr,
            drug_name=entities.drug_names[0] if entities.drug_names else None,
        )
    )
    chunks, mcp_data = await asyncio.gather(qdrant_task, mcp_task)

    # [5] Safety pre-check
    scores = [c.get("score", 0.0) for c in chunks]
    safety = pre_generation_check(entities, scores)

    # Emit sources
    sources = [
        {"source": c.get("source", ""), "type": c.get("type", ""), "name": c.get("name", ""), "score": c.get("score", 0.0)}
        for c in chunks
    ]
    yield {"type": "sources", "value": sources}

    if safety.should_block:
        yield {"type": "token", "value": safety.override_response or ""}
        yield {"type": "done", "confidence": safety.confidence, "is_urgent": safety.is_urgent}
        return

    # [6] Stream LLM tokens
    full_response = ""
    async for token in generate_stream(
        user_message=user_message,
        context_chunks=chunks,
        mcp_data=mcp_data,
        response_lang=detected_lang,
    ):
        full_response += token
        yield {"type": "token", "value": token}

    # [7] Post-check — append disclaimers as final tokens
    checked = post_generation_check(full_response, safety.disclaimers)
    extra = checked[len(full_response):]
    if extra:
        yield {"type": "token", "value": extra}

    yield {"type": "done", "confidence": safety.confidence, "is_urgent": False}


async def _safe_hybrid_search(query_fr: str, icd10_codes: list[str]) -> list[dict]:
    """Qdrant hybrid search with fallback on error."""
    try:
        return hybrid_search(
            query_text=query_fr,
            limit=5,
            icd10_filter=icd10_codes if icd10_codes else None,
        )
    except Exception:
        return []
