"""
Qdrant vector store with Hybrid Search (Dense + BM25 + RRF + type boost).

Collection schema:
  - Dense vectors: 768-dim (multilingual-e5-base), Cosine distance
  - Sparse vectors: BM25 via Qdrant's built-in sparse indexing
  - Payload: source, type, name, icd10_codes, language, section, text

Retrieval strategy (up to 5 RRF prefetch paths):
  1. Dense unfiltered (limit=30) — broad semantic recall
  2. BM25 clinical (limit=30) — keyword matches, guidelines excluded
  3. Disease-type boost (always, limit=10) — focused disease chunk injection
  4. Drug-type boost (conditional, limit=10) — only when drug entities detected
  5. ICD-10 boost (conditional, limit=15) — code-specific retrieval

BM25 excludes guidelines because HAS/SMR chunks share drug/disease vocabulary
and generate keyword false positives that flood the RRF candidate pool.

Why type boosts?
  Without them, HAS/SMR guideline chunks dominate the candidate pool
  (BM25 false positives + dense semantic overlap). The disease boost is
  unconditional because symptom queries are the primary use case. The drug
  boost is conditional to avoid diluting the disease boost on symptom queries.
"""
from typing import Any

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Prefetch,
    FusionQuery,
    Fusion,
)

from app.api.v1.endpoints.metrics import rag_retrieval_latency_seconds
from app.core.config import get_settings
from app.rag.embedder import embed_query, EMBEDDING_DIM
from app.rag.bm25_tokenizer import build_sparse_query

COLLECTION_NAME = "medisense_medical"

# RRF prefetch limits — base paths provide broad recall; type boosts inject
# small focused sets. BM25 excludes guidelines to prevent HAS/SMR noise.
_PREFETCH_LIMIT = 30           # dense (unfiltered) + BM25 (guideline-excluded)
_TYPE_BOOST_LIMIT = 10         # disease/drug boost — small focused injection
_ICD10_BOOST_LIMIT = 15        # ICD-10 boost — code-specific retrieval


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
    """Build sparse query vector using the shared BM25 tokenizer.

    Uses stopword removal, accent stripping, and clinical bigrams
    to focus BM25 matching on meaningful medical terms.
    """
    return build_sparse_query(text)


def hybrid_search(
    query_text: str,
    limit: int = 5,
    source_filter: str | None = None,
    icd10_filter: list[str] | None = None,
    has_drug_entity: bool = False,
) -> list[dict[str, Any]]:
    """
    Hybrid search: Dense (semantic) + BM25 (keyword) merged via RRF.

    Returns top `limit` results with payload and score.

    Optional filters:
      - source_filter: restrict to a single source ("ansm", "icd10", "has", "pubmed")
      - icd10_filter: boost/restrict by ICD-10 codes
      - has_drug_entity: when True, adds a drug-type boost prefetch
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
    # Dense path: unfiltered for broad recall.
    # BM25 path: excludes guidelines to prevent HAS/SMR keyword false positives.
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
        exclude_guideline = FieldCondition(key="type", match=MatchValue(value="guideline"))
        bm25_filter = (
            Filter(must=base_conditions, must_not=exclude_guideline)
            if base_conditions
            else Filter(must_not=exclude_guideline)
        )
        prefetches.append(
            Prefetch(
                query=sparse_query,
                using="bm25",
                limit=_PREFETCH_LIMIT,
                filter=bm25_filter,
            )
        )

    # Disease-type boost: always active — ensures disease/condition chunks are
    # represented even when HAS/SMR guideline chunks dominate the base paths.
    disease_conditions = [*base_conditions, FieldCondition(key="type", match=MatchValue(value="disease"))]
    prefetches.append(
        Prefetch(
            query=query_vector,
            using="dense",
            limit=_TYPE_BOOST_LIMIT,
            filter=Filter(must=disease_conditions),
        )
    )

    # Drug-type boost: conditional — only when entity extraction detects drug
    # names.  Unconditional drug boost dilutes disease boost on symptom queries.
    if has_drug_entity:
        drug_conditions = [*base_conditions, FieldCondition(key="type", match=MatchValue(value="drug"))]
        prefetches.append(
            Prefetch(
                query=query_vector,
                using="dense",
                limit=_TYPE_BOOST_LIMIT,
                filter=Filter(must=drug_conditions),
            )
        )

    # Soft ICD-10 boost path (extra prefetch + RRF fusion) instead of hard filtering.
    if icd10_filter:
        icd10_conditions = [*base_conditions, FieldCondition(key="icd10_codes", match=MatchAny(any=icd10_filter))]
        prefetches.append(
            Prefetch(
                query=query_vector,
                using="dense",
                limit=_ICD10_BOOST_LIMIT,
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
