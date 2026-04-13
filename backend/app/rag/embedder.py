"""
Embedding service using intfloat/multilingual-e5-base.

Why this model?
  - 768-dim embeddings, good balance of size vs quality
  - Trained on 100+ languages including Arabic and French
  - Outperforms nomic-embed-text for Arabic/Darija queries
  - E5 instruction format: prefix "query: " or "passage: " for asymmetric retrieval

Why sentence-transformers?
  - Standard library for embedding models
  - Handles tokenization, batching, normalization
  - Cross-encoder support from the same library (reranker.py)
"""
from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-base"
EMBEDDING_DIM = 768


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load the model once and cache it for the process lifetime."""
    return SentenceTransformer(MODEL_NAME)


def embed_query(text: str) -> list[float]:
    """
    Embed a user query.

    E5 models require "query: " prefix for queries (asymmetric retrieval).
    """
    model = _get_model()
    vector = model.encode(f"query: {text}", normalize_embeddings=True)
    return vector.tolist()


def embed_passage(text: str) -> list[float]:
    """
    Embed a document passage for indexing.

    E5 models require "passage: " prefix for documents.
    """
    model = _get_model()
    vector = model.encode(f"passage: {text}", normalize_embeddings=True)
    return vector.tolist()


def embed_passages_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """
    Batch-embed multiple passages for bulk indexing.

    Used by ingest_medical_corpus.py to index 84k chunks efficiently.
    """
    model = _get_model()
    prefixed = [f"passage: {t}" for t in texts]
    vectors = model.encode(prefixed, normalize_embeddings=True, batch_size=batch_size, show_progress_bar=True)
    return vectors.tolist()
