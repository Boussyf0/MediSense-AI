"""
Embedding service using Jina AI hosted embeddings (jina-embeddings-v3).

Why hosted (vs a local sentence-transformers model)?
  - The local multilingual-e5 model is ~1GB resident and OOM-killed the API box.
  - Jina v3 is strong multilingual (French / Arabic / Darija) — fits the medical corpus.
  - Hosted = the API container stays small; embedding is a lightweight HTTP call.

Model: jina-embeddings-v3, 1024-dim, cosine. Task-specific LoRA:
  - "retrieval.query"   for user queries   (asymmetric retrieval)
  - "retrieval.passage" for indexed documents

Drop-in replacement: same public interface (embed_query / embed_passage /
embed_passages_batch / EMBEDDING_DIM) as the previous local implementation.
"""
from __future__ import annotations

import time

import httpx

from app.core.config import get_settings

JINA_URL = "https://api.jina.ai/v1/embeddings"
MODEL_NAME = "jina-embeddings-v3"
EMBEDDING_DIM = 1024
_TIMEOUT = 60.0
_MAX_RETRIES = 6


def _embed(texts: list[str], task: str) -> list[list[float]]:
    """Call the Jina embeddings API and return vectors in input order.

    Retries with exponential backoff on rate limits (429) and transient 5xx,
    so bulk ingestion and the live chat path both survive the free-tier limits.
    """
    settings = get_settings()
    if not settings.JINA_API_KEY:
        raise RuntimeError("JINA_API_KEY is not set — embeddings unavailable")

    payload = {
        "model": MODEL_NAME,
        "task": task,
        "dimensions": EMBEDDING_DIM,
        "normalized": True,          # L2-normalized → cosine == dot product
        "embedding_type": "float",
        "input": texts,
    }
    headers = {
        "Authorization": f"Bearer {settings.JINA_API_KEY}",
        "Content-Type": "application/json",
    }

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        resp = httpx.post(JINA_URL, headers=headers, json=payload, timeout=_TIMEOUT)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = float(resp.headers.get("retry-after", 2 ** attempt))
            last_exc = httpx.HTTPStatusError(
                f"Jina {resp.status_code}", request=resp.request, response=resp
            )
            time.sleep(min(wait, 30))
            continue
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda d: d["index"])  # preserve input order
        return [d["embedding"] for d in data]

    raise RuntimeError(f"Jina embeddings failed after {_MAX_RETRIES} retries") from last_exc


def embed_query(text: str) -> list[float]:
    """Embed a single user query."""
    return _embed([text], task="retrieval.query")[0]


def embed_passage(text: str) -> list[float]:
    """Embed a single document passage for indexing."""
    return _embed([text], task="retrieval.passage")[0]


def embed_passages_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Batch-embed passages for bulk indexing (chunked to respect API limits)."""
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        out.extend(_embed(texts[i : i + batch_size], task="retrieval.passage"))
    return out
