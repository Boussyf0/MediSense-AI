"""
RAG Pipeline Orchestrator — full execution path.

Steps:
  [0] IoT context fetch (US-13) — biometric anomalies from last 30 days
  [1] Language detection (langdetect + Darija stopwords)
  [2] Query normalization (Darija/AR → clinical French via Mistral)
  [3] Parallel retrieval:
      [3a] Qdrant dense + BM25 hybrid (RRF) — top-20 candidates
      [3b] MCP servers (ANSM + ICD-11) with circuit breaker
      [3c] Cross-encoder reranking (mmarco) — top-20 → top-5 (US-12)
  [4] Medical entity extraction + ICD-10 payload boost
  [5] Safety pre-check (confidence gate, urgency detection, IoT critical override)
  [6] LLM generation (Mistral 7B, streaming or blocking)
  [7] Safety post-check (dosage warnings, disclaimers)
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.language import detect_language
from app.rag.normalizer import normalize_to_french
from app.rag.medical_entities import extract_entities
from app.rag.vectorstore import hybrid_search
from app.rag.reranker import rerank
from app.rag.safety import pre_generation_check, post_generation_check
from app.rag.llm import generate, generate_stream
from app.rag.iot_context import fetch_iot_context, IoTContext
from app.mcp.client import fetch_mcp_context


logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Full result from the RAG pipeline (non-streaming mode)."""
    reply: str
    sources: list[dict[str, Any]]
    language: str
    confidence: float
    is_urgent: bool
    mcp_data: dict[str, Any]
    query_fr: str           # normalized French query (for audit/debug)
    iot_context: IoTContext | None = None
    timings_ms: dict[str, float] | None = None


async def run(
    user_message: str,
    patient_allergies: list[str] | None = None,
    patient_id: str | None = None,
    db: AsyncSession | None = None,
) -> PipelineResult:
    """
    Execute the full RAG pipeline (non-streaming).

    Args:
        user_message      : Raw patient message in any supported language.
        patient_allergies : Optional known patient allergies (from profile).
        patient_id        : Patient UUID — enables IoT context injection (US-13).
        db                : Async DB session — required for IoT context fetch.

    Returns:
        PipelineResult with reply, sources, confidence, iot_context, etc.
    """
    started = time.perf_counter()
    timings_ms: dict[str, float] = {}

    # [0] IoT context fetch (US-13) — gracefully returns empty on failure
    t0 = time.perf_counter()
    iot_ctx = await fetch_iot_context(patient_id, db)
    timings_ms["iot_context"] = (time.perf_counter() - t0) * 1000

    # Critical IoT anomaly → escalate immediately, skip LLM
    if iot_ctx.has_critical:
        critical_names = [
            f"{a['metric']}={a['value']}{a.get('unit','')}"
            for a in iot_ctx.anomalies
            if a["severity"] == "critical"
        ]
        iot_override = (
            f"ALERTE IoT CRITIQUE: Anomalies biométriques détectées: "
            f"{', '.join(critical_names)}. "
            f"Consultez immédiatement un médecin ou appelez le 141 (SAMU Maroc)."
        )
        return PipelineResult(
            reply=iot_override,
            sources=[],
            language="fr",
            confidence=1.0,
            is_urgent=True,
            mcp_data={},
            query_fr=user_message,
            iot_context=iot_ctx,
            timings_ms=timings_ms,
        )

    # [1] Language detection
    t0 = time.perf_counter()
    detected_lang = detect_language(user_message)
    timings_ms["language_detection"] = (time.perf_counter() - t0) * 1000

    # [2] Normalize to French
    t0 = time.perf_counter()
    query_fr = await normalize_to_french(user_message, detected_lang)
    timings_ms["normalization"] = (time.perf_counter() - t0) * 1000

    # [4] Extract medical entities (from French query)
    t0 = time.perf_counter()
    entities = extract_entities(query_fr)
    timings_ms["entity_extraction"] = (time.perf_counter() - t0) * 1000

    # [3] Parallel: Qdrant retrieval + MCP fetch
    t0 = time.perf_counter()
    qdrant_task = asyncio.create_task(
        _safe_hybrid_search(query_fr, entities.icd10_codes, bool(entities.drug_names))
    )
    mcp_task = asyncio.create_task(
        fetch_mcp_context(
            query_fr,
            drug_name=entities.drug_names[0] if entities.drug_names else None,
        )
    )

    chunks, mcp_data = await asyncio.gather(qdrant_task, mcp_task)
    timings_ms["retrieval_and_mcp"] = (time.perf_counter() - t0) * 1000

    # [3c] Type diversification + cross-encoder reranking (US-12)
    chunks = _diversify_by_type(chunks)
    t0 = time.perf_counter()
    chunks = _safe_rerank(query_fr, chunks, top_k=5)
    timings_ms["rerank"] = (time.perf_counter() - t0) * 1000

    # [5] Safety pre-check
    t0 = time.perf_counter()
    scores = [c.get("score", 0.0) for c in chunks]
    safety = pre_generation_check(entities, scores, query_text=query_fr)
    timings_ms["safety_precheck"] = (time.perf_counter() - t0) * 1000

    if safety.should_block:
        timings_ms["total"] = (time.perf_counter() - started) * 1000
        logger.info("pipeline_timing_ms=%s", {k: round(v, 2) for k, v in timings_ms.items()})
        return PipelineResult(
            reply=safety.override_response or "",
            sources=[],
            language=detected_lang,
            confidence=safety.confidence,
            is_urgent=safety.is_urgent,
            mcp_data=mcp_data,
            query_fr=query_fr,
            timings_ms=timings_ms,
        )

    # [6] LLM generation
    t0 = time.perf_counter()
    raw_reply = await generate(
        user_message=user_message,
        context_chunks=chunks,
        mcp_data=mcp_data,
        response_lang=detected_lang,
    )
    timings_ms["generation"] = (time.perf_counter() - t0) * 1000

    # [7] Safety post-check
    t0 = time.perf_counter()
    reply = post_generation_check(raw_reply, safety.disclaimers, patient_allergies)
    timings_ms["safety_postcheck"] = (time.perf_counter() - t0) * 1000
    timings_ms["total"] = (time.perf_counter() - started) * 1000
    logger.info("pipeline_timing_ms=%s", {k: round(v, 2) for k, v in timings_ms.items()})

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
        iot_context=iot_ctx,
        timings_ms=timings_ms,
    )


async def run_stream(
    user_message: str,
    patient_allergies: list[str] | None = None,
    patient_id: str | None = None,
    db: AsyncSession | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Execute the RAG pipeline with SSE streaming.

    Yields event dicts suitable for Server-Sent Events:
      {"type": "lang",    "value": "darija"}
      {"type": "iot",     "value": [{anomaly}, ...]}
      {"type": "sources", "value": [{...}]}
      {"type": "token",   "value": "Selon"}
      {"type": "done",    "confidence": 0.82}

    Args:
        user_message      : Raw patient message.
        patient_allergies : Known patient allergies.
        patient_id        : Patient UUID — enables IoT context injection (US-13).
        db                : Async DB session — required for IoT context fetch.
    """
    started = time.perf_counter()
    timings_ms: dict[str, float] = {}

    # [0] IoT context fetch (US-13)
    t0 = time.perf_counter()
    iot_ctx = await fetch_iot_context(patient_id, db)
    timings_ms["iot_context"] = (time.perf_counter() - t0) * 1000
    if not iot_ctx.is_empty:
        yield {"type": "iot", "value": iot_ctx.anomalies}

    # Critical IoT anomaly → escalate immediately, skip LLM
    if iot_ctx.has_critical:
        critical_names = [
            f"{a['metric']}={a['value']}{a.get('unit','')}"
            for a in iot_ctx.anomalies
            if a["severity"] == "critical"
        ]
        iot_override = (
            f"ALERTE IoT CRITIQUE: Anomalies biométriques détectées: "
            f"{', '.join(critical_names)}. "
            f"Consultez immédiatement un médecin ou appelez le 141 (SAMU Maroc)."
        )
        yield {"type": "token", "value": iot_override}
        timings_ms["total"] = (time.perf_counter() - started) * 1000
        yield {"type": "done", "confidence": 1.0, "is_urgent": True, "timings_ms": timings_ms}
        return

    # [1] Language detection
    t0 = time.perf_counter()
    detected_lang = detect_language(user_message)
    timings_ms["language_detection"] = (time.perf_counter() - t0) * 1000
    yield {"type": "lang", "value": detected_lang}

    # [2] Normalize to French
    t0 = time.perf_counter()
    query_fr = await normalize_to_french(user_message, detected_lang)
    timings_ms["normalization"] = (time.perf_counter() - t0) * 1000

    # [4] Extract medical entities
    t0 = time.perf_counter()
    entities = extract_entities(query_fr)
    timings_ms["entity_extraction"] = (time.perf_counter() - t0) * 1000

    # [3] Parallel retrieval
    t0 = time.perf_counter()
    qdrant_task = asyncio.create_task(
        _safe_hybrid_search(query_fr, entities.icd10_codes, bool(entities.drug_names))
    )
    mcp_task = asyncio.create_task(
        fetch_mcp_context(
            query_fr,
            drug_name=entities.drug_names[0] if entities.drug_names else None,
        )
    )
    chunks, mcp_data = await asyncio.gather(qdrant_task, mcp_task)
    timings_ms["retrieval_and_mcp"] = (time.perf_counter() - t0) * 1000

    # [3c] Type diversification + cross-encoder reranking (US-12)
    chunks = _diversify_by_type(chunks)
    t0 = time.perf_counter()
    chunks = _safe_rerank(query_fr, chunks, top_k=5)
    timings_ms["rerank"] = (time.perf_counter() - t0) * 1000

    # [5] Safety pre-check
    t0 = time.perf_counter()
    scores = [c.get("score", 0.0) for c in chunks]
    safety = pre_generation_check(entities, scores, query_text=query_fr)
    timings_ms["safety_precheck"] = (time.perf_counter() - t0) * 1000

    # Emit sources
    sources = [
        {"source": c.get("source", ""), "type": c.get("type", ""), "name": c.get("name", ""), "score": c.get("score", 0.0)}
        for c in chunks
    ]
    yield {"type": "sources", "value": sources}

    if safety.should_block:
        yield {"type": "token", "value": safety.override_response or ""}
        timings_ms["total"] = (time.perf_counter() - started) * 1000
        yield {
            "type": "done",
            "confidence": safety.confidence,
            "is_urgent": safety.is_urgent,
            "timings_ms": {k: round(v, 2) for k, v in timings_ms.items()},
        }
        return

    # [6] Stream LLM tokens
    full_response = ""
    generation_started = time.perf_counter()
    first_token_ms: float | None = None
    async for token in generate_stream(
        user_message=user_message,
        context_chunks=chunks,
        mcp_data=mcp_data,
        response_lang=detected_lang,
    ):
        if first_token_ms is None:
            first_token_ms = (time.perf_counter() - generation_started) * 1000
        full_response += token
        yield {"type": "token", "value": token}
    timings_ms["generation"] = (time.perf_counter() - generation_started) * 1000
    if first_token_ms is not None:
        timings_ms["first_token"] = first_token_ms

    # [7] Post-check — append disclaimers as final tokens
    t0 = time.perf_counter()
    checked = post_generation_check(full_response, safety.disclaimers, patient_allergies)
    timings_ms["safety_postcheck"] = (time.perf_counter() - t0) * 1000
    extra = checked[len(full_response):]
    if extra:
        yield {"type": "token", "value": extra}

    timings_ms["total"] = (time.perf_counter() - started) * 1000
    yield {
        "type": "done",
        "confidence": safety.confidence,
        "is_urgent": False,
        "timings_ms": {k: round(v, 2) for k, v in timings_ms.items()},
    }


async def _safe_hybrid_search(
    query_fr: str,
    icd10_codes: list[str],
    has_drug_entity: bool = False,
) -> list[dict]:
    """Qdrant hybrid search — fetches top-20 candidates for cross-encoder reranking."""
    try:
        return hybrid_search(
            query_text=query_fr,
            limit=20,
            icd10_filter=icd10_codes if icd10_codes else None,
            has_drug_entity=has_drug_entity,
        )
    except Exception:
        return []


_MAX_GUIDELINE_CHUNKS = 3


def _diversify_by_type(chunks: list[dict]) -> list[dict]:
    """Cap guideline chunks to prevent HAS/SMR noise from dominating the CE pool.

    Without this, symptom queries return ~16/20 guideline chunks from the base
    dense + BM25 paths, leaving the CE with too few disease/drug candidates.
    Capping guidelines at 5/20 (25%) forces the remaining slots to be filled by
    disease and drug chunks that the CE can properly rank.
    """
    guideline_count = 0
    result = []
    for chunk in chunks:
        if chunk.get("type") == "guideline":
            guideline_count += 1
            if guideline_count > _MAX_GUIDELINE_CHUNKS:
                continue
        result.append(chunk)
    return result


def _safe_rerank(query_fr: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """Cross-encoder reranking with graceful fallback to RRF order on failure."""
    if not chunks:
        return chunks
    try:
        ranked = rerank(query_fr, chunks, top_k=top_k)
        return [r.chunk for r in ranked]
    except Exception:
        logger.warning("cross-encoder rerank failed, falling back to RRF order")
        return chunks[:top_k]
