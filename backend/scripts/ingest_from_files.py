#!/usr/bin/env python3
"""
Ingest pre-built corpus files into Qdrant.

Reads JSON files from data/real_corpus/ and upserts into Qdrant.
Run this inside Docker AFTER running build_corpus_local.py on the host.

Usage:
  docker exec medisense_fastapi python scripts/ingest_from_files.py
"""
import json
import hashlib
import uuid
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("POSTGRES_PASSWORD", "dummy")
os.environ.setdefault("REDIS_PASSWORD", "dummy")
os.environ.setdefault("JWT_SECRET_KEY", "dummy")
os.environ.setdefault("PGCRYPTO_KEY", "dummy")

from app.rag.embedder import embed_passages_batch
from app.rag.vectorstore import ensure_collection, upsert_points, get_collection_info

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "real_corpus"
FILES = [
    "icd10_full.json",
    "ansm_drugs.json",  # intact
    "has_guidelines.json",
    "bdpm_france.json",
    "extended_drugs.json",
    "drug_interactions.json",
    "biological_references.json",
    "moroccan_protocols_extended.json",
    "clinical_pharmacology.json",
]


def _uid(text: str) -> str:
    return str(uuid.UUID(hashlib.md5(text.encode()).hexdigest()))


def main():
    print("=" * 60)
    print("MediSense Corpus Ingestion from Files")
    print("=" * 60)

    ensure_collection()

    all_chunks = []
    for filename in FILES:
        path = DATA_DIR / filename
        if not path.exists():
            print(f"  [SKIP] {filename} not found")
            continue
        with open(path, encoding="utf-8") as f:
            chunks = json.load(f)
        print(f"  Loaded {len(chunks):,} chunks from {filename}")
        all_chunks.extend(chunks)

    if not all_chunks:
        print("No chunks found. Run build_corpus_local.py on the host first.")
        sys.exit(1)

    print(f"\nTotal: {len(all_chunks):,} chunks to embed and upsert")

    print(f"\n[1/2] Computing embeddings (multilingual-e5-base)...")
    texts = [c["text"] for c in all_chunks]
    vectors = embed_passages_batch(texts, batch_size=64)
    print(f"  Dimension: {len(vectors[0])}")

    print(f"\n[2/2] Upserting {len(all_chunks):,} points...")
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

    total = upsert_points(points, batch_size=100)
    info = get_collection_info()

    print(f"\n{'='*60}")
    print(f"Done. Collection '{info['name']}': {info['points_count']:,} points, status={info['status']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
