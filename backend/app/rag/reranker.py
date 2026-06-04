"""
Cross-encoder re-ranker — in the hot path for clinical safety.

Model: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 (multilingual MS MARCO)

Architecture:
  1. Pipeline retrieves top-20 candidates via Qdrant RRF (Dense + BM25)
  2. Cross-encoder scores all 20 (query, passage) pairs jointly
  3. Top-5 by CE score are passed to the LLM for generation

Why CE in the hot path (not eval-only)?
  - Rerank evaluation (sprint 3) showed ρ=0.09 between RRF and CE rankings
  - 8/20 clinical queries had NEGATIVE correlation under RRF alone
  - Safety-critical queries (embolie pulmonaire, céphalée intense) were misranked
  - The ~500-1000ms latency overhead is acceptable for clinical safety

This satisfies US-12: "Cross-encoder re-ranking sur top-20 chunks" by placing
the CE in the hot path with graceful fallback to RRF order on failure.

Graceful degradation:
  If the cross-encoder fails (model load error, OOM), the pipeline falls
  back to RRF ordering — see _safe_rerank() in pipeline.py.
"""
from functools import lru_cache
from dataclasses import dataclass

from sentence_transformers import CrossEncoder

from app.api.v1.endpoints.metrics import rag_retrieval_latency_seconds

MODEL_NAME = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


@lru_cache(maxsize=1)
def _get_model() -> CrossEncoder:
    """Load the cross-encoder once and cache it."""
    return CrossEncoder(MODEL_NAME, max_length=512)


@dataclass
class RerankedChunk:
    """A chunk with its cross-encoder score."""
    chunk: dict
    ce_score: float
    original_rank: int


def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[RerankedChunk]:
    """
    Re-rank chunks using the multilingual cross-encoder.

    Args:
        query: The user query (in French, post-normalization).
        chunks: List of chunks from Qdrant (each must have a 'text' key).
        top_k: Number of top results to return.

    Returns:
        Top-k chunks sorted by cross-encoder score (descending).
    """
    if not chunks:
        return []

    model = _get_model()

    # Build (query, passage) pairs for the cross-encoder
    pairs = [(query, chunk.get("text", "")) for chunk in chunks]

    # Score all pairs
    with rag_retrieval_latency_seconds.labels(stage="rerank").time():
        scores = model.predict(pairs)

    # Combine with original data
    ranked = [
        RerankedChunk(chunk=chunk, ce_score=float(score), original_rank=i)
        for i, (chunk, score) in enumerate(zip(chunks, scores))
    ]

    # Sort by cross-encoder score (descending)
    ranked.sort(key=lambda x: x.ce_score, reverse=True)

    return ranked[:top_k]


def evaluate_rrf_vs_crossencoder(
    query: str,
    rrf_chunks: list[dict],
) -> dict:
    """
    Compare RRF ranking vs cross-encoder ranking.

    Returns metrics:
      - rank_correlation: Spearman correlation between RRF and CE rankings
      - top3_overlap: fraction of top-3 results that agree
      - mrr_rrf: Mean Reciprocal Rank of best CE result in RRF ranking
    """
    if not rrf_chunks:
        return {"rank_correlation": 0.0, "top3_overlap": 0.0, "mrr_rrf": 0.0}

    # Get cross-encoder re-ranking
    ce_ranked = rerank(query, rrf_chunks, top_k=len(rrf_chunks))

    # Build ID-based rank maps
    rrf_ids = [c.get("id", str(i)) for i, c in enumerate(rrf_chunks)]
    ce_ids = [r.chunk.get("id", str(r.original_rank)) for r in ce_ranked]

    # Top-3 overlap
    rrf_top3 = set(rrf_ids[:3])
    ce_top3 = set(ce_ids[:3])
    top3_overlap = len(rrf_top3 & ce_top3) / 3.0

    # MRR: where does the CE #1 appear in RRF?
    ce_best_id = ce_ids[0] if ce_ids else None
    mrr_rrf = 0.0
    if ce_best_id and ce_best_id in rrf_ids:
        mrr_rrf = 1.0 / (rrf_ids.index(ce_best_id) + 1)

    # Spearman rank correlation (simplified)
    n = len(rrf_ids)
    if n < 2:
        rank_corr = 1.0
    else:
        ce_rank_map = {id_: rank for rank, id_ in enumerate(ce_ids)}
        d_squared_sum = sum(
            (i - ce_rank_map.get(id_, n)) ** 2
            for i, id_ in enumerate(rrf_ids)
        )
        rank_corr = 1 - (6 * d_squared_sum) / (n * (n**2 - 1))

    return {
        "rank_correlation": round(rank_corr, 4),
        "top3_overlap": round(top3_overlap, 4),
        "mrr_rrf": round(mrr_rrf, 4),
        "rrf_top3": rrf_ids[:3],
        "ce_top3": ce_ids[:3],
    }
