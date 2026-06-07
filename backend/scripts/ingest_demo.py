"""Curated demo ingestion — embeds a high-value subset of the medical corpus
into Qdrant via the (hosted Jina) embedder.

The full corpus is ~83k chunks (bdpm_france alone is 63k) which is too large for
the embedding free tier and slow. For a demo we ingest the most useful clinical
references plus capped slices of the big drug/ICD files — a few thousand chunks,
which is plenty for grounded Q&A.

Run (against the Fly Qdrant via a tunnel on 6433):
  cd backend
  QDRANT_HOST=localhost QDRANT_PORT=6433 JINA_API_KEY=... \
  POSTGRES_PASSWORD=x REDIS_PASSWORD=x JWT_SECRET_KEY=x PGCRYPTO_KEY=x \
  ../venv/bin/python scripts/ingest_demo.py
"""
import hashlib
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.embedder import embed_passages_batch
from app.rag.vectorstore import ensure_collection, get_collection_info, upsert_points

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "real_corpus"

# filename -> max chunks to take (None = all)
CURATED = {
    "has_guidelines.json": None,
    "drug_interactions.json": None,
    "clinical_pharmacology.json": None,
    "biological_references.json": None,
    "moroccan_protocols_extended.json": None,
    "ansm_drugs.json": 1200,
    "extended_drugs.json": 600,
    "icd10_full.json": 800,
}


def _uid(text: str) -> str:
    return str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))


def main() -> None:
    ensure_collection()

    all_chunks = []
    for filename, cap in CURATED.items():
        path = DATA_DIR / filename
        if not path.exists():
            print(f"  [SKIP] {filename} not found")
            continue
        with open(path, encoding="utf-8") as f:
            chunks = json.load(f)
        if cap:
            chunks = chunks[:cap]
        # keep only well-formed chunks with text
        chunks = [c for c in chunks if isinstance(c, dict) and c.get("text")]
        print(f"  + {len(chunks):,} from {filename}")
        all_chunks.extend(chunks)

    print(f"\nTotal: {len(all_chunks):,} chunks to embed (Jina) and upsert")

    texts = [c["text"] for c in all_chunks]
    vectors = embed_passages_batch(texts, batch_size=64)
    print(f"  embedded, dim={len(vectors[0])}")

    points = []
    for chunk, vector in zip(all_chunks, vectors):
        token_freq: dict[int, float] = {}
        for token in chunk["text"].lower().split():
            idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % 100_000
            token_freq[idx] = token_freq.get(idx, 0) + 1.0
        points.append({
            "id": _uid(chunk["text"]),
            "dense_vector": vector,
            "sparse_indices": list(token_freq.keys()),
            "sparse_values": list(token_freq.values()),
            "payload": chunk,
        })

    upsert_points(points, batch_size=100)
    info = get_collection_info()
    print(f"\nDone. Collection '{info['name']}': {info['points_count']:,} points, status={info['status']}")


if __name__ == "__main__":
    main()
