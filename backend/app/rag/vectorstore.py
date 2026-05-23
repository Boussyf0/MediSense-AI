"""
Qdrant vector store with Hybrid Search (Dense + BM25 + RRF).

Collection schema:
  - Dense vectors: 768-dim (multilingual-e5-base), Cosine distance
  - Sparse vectors: BM25 via Qdrant's built-in sparse indexing
  - Payload: source, type, name, icd10_codes, language, section, text

Why Qdrant hybrid search?
  Dense search captures semantic similarity ("headache" ~ "cephalee").
  BM25 captures exact keyword matches ("ibuprofene 400mg").
  Reciprocal Rank Fusion (RRF) merges both ranked lists — near cross-encoder
  accuracy at ~15ms instead of ~200ms.
"""
import hashlib
import uuid
from typing import Any

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    NamedVector,
    NamedSparseVector,
    SparseVector,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    SearchParams,
    Prefetch,
    FusionQuery,
    Fusion,
)

from app.api.v1.endpoints.metrics import rag_retrieval_latency_seconds
from app.core.config import get_settings
from app.rag.embedder import embed_query, EMBEDDING_DIM

COLLECTION_NAME = "medisense_medical"

# RRF top-k per sub-query before fusion
_PREFETCH_LIMIT = 20
_ICD10_BOOST_PREFETCH_LIMIT = 12


def _get_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


def ensure_collection() -> None:
    """
    Create the collection if it doesn't exist.

    Called once at startup and by the ingestion script.
    """
    client = _get_client()

    if client.collection_exists(COLLECTION_NAME):
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE,
                on_disk=True,
            ),
        },
        sparse_vectors_config={
            "bm25": SparseVectorParams(
                index=SparseIndexParams(on_disk=True),
            ),
        },
    )

    # Payload indices for filtered search
    for field in ("source", "type", "language"):
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="icd10_codes",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )


def upsert_points(
    points: list[dict[str, Any]],
    batch_size: int = 100,
) -> int:
    """
    Upsert points into the collection.

    Each point dict must have:
      - "id": str (UUID)
      - "dense_vector": list[float]
      - "sparse_indices": list[int]   (BM25 token indices)
      - "sparse_values": list[float]  (BM25 token weights)
      - "payload": dict
    """
    client = _get_client()
    total = 0

    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        structs = [
            PointStruct(
                id=p["id"],
                vector={
                    "dense": p["dense_vector"],
                    "bm25": SparseVector(
                        indices=p["sparse_indices"],
                        values=p["sparse_values"],
                    ),
                },
                payload=p["payload"],
            )
            for p in batch
        ]
        client.upsert(collection_name=COLLECTION_NAME, points=structs)
        total += len(structs)

    return total


def _build_sparse_query(text: str) -> SparseVector | None:
    """Build sparse query vector using the same deterministic hashing as ingestion."""
    token_freq: dict[int, float] = {}
    for token in text.lower().split():
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % 100_000
        token_freq[idx] = token_freq.get(idx, 0.0) + 1.0

    if not token_freq:
        return None

    return SparseVector(
        indices=list(token_freq.keys()),
        values=list(token_freq.values()),
    )


def hybrid_search(
    query_text: str,
    limit: int = 5,
    source_filter: str | None = None,
    icd10_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Hybrid search: Dense (semantic) + BM25 (keyword) merged via RRF.

    Returns top `limit` results with payload and score.

    Optional filters:
      - source_filter: restrict to a single source ("ansm", "icd10", "has", "pubmed")
      - icd10_filter: boost/restrict by ICD-10 codes
    """
    client = _get_client()
    with rag_retrieval_latency_seconds.labels(stage="dense").time():
        query_vector = embed_query(query_text)

    # Build base filter (strict only for source). ICD-10 is applied as a BOOST path,
    # not as a hard filter, so sources without icd10_codes (e.g. BDPM) can still surface.
    base_conditions = []
    if source_filter:
        base_conditions.append(FieldCondition(key="source", match=MatchValue(value=source_filter)))

    search_filter = Filter(must=base_conditions) if base_conditions else None

    # Hybrid search using Qdrant's query API with RRF fusion.
    # Dense path: embed the query and search by cosine similarity.
    # BM25 path: use the same deterministic sparse hashing as ingestion.
    with rag_retrieval_latency_seconds.labels(stage="bm25").time():
        sparse_query = _build_sparse_query(query_text)
    prefetches = [
        Prefetch(
            query=query_vector,
            using="dense",
            limit=_PREFETCH_LIMIT,
            filter=search_filter,
        ),
    ]
    if sparse_query is not None:
        prefetches.append(
            Prefetch(
                query=sparse_query,
                using="bm25",
                limit=_PREFETCH_LIMIT,
                filter=search_filter,
            )
        )

    # Soft ICD-10 boost path (extra prefetch + RRF fusion) instead of hard filtering.
    if icd10_filter:
        icd10_conditions = [*base_conditions, FieldCondition(key="icd10_codes", match=MatchAny(any=icd10_filter))]
        prefetches.append(
            Prefetch(
                query=query_vector,
                using="dense",
                limit=_ICD10_BOOST_PREFETCH_LIMIT,
                filter=Filter(must=icd10_conditions),
            )
        )

    with rag_retrieval_latency_seconds.labels(stage="rrf").time():
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=prefetches,
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
        )

    return [
        {
            "id": str(point.id),
            "score": point.score,
            **point.payload,
        }
        for point in results.points
    ]


def get_collection_info() -> dict[str, Any]:
    """Return collection stats (for health checks and monitoring)."""
    client = _get_client()
    info = client.get_collection(COLLECTION_NAME)
    return {
        "name": COLLECTION_NAME,
        "points_count": info.points_count,
        "vectors_count": info.vectors_count,
        "status": info.status.value,
    }
