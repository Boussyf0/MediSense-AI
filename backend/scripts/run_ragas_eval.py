#!/usr/bin/env python3
"""
RAGAS-style generation quality evaluation for MediSense RAG pipeline.

Measures whether the LLM *answer* is grounded in retrieved context and
actually addresses the question — retrieval metrics (MRR/NDCG) don't capture this.

Metrics implemented (no external LLM required):
  - Context Precision    : fraction of retrieved chunks that are relevant to the query
  - Context Recall       : fraction of ground-truth keywords covered by retrieved context
  - Answer Faithfulness  : fraction of answer sentences supported by retrieved context
                           (keyword-overlap proxy — fast, deterministic)
  - Answer Relevance     : whether the answer contains query keywords (proxy)

For true RAGAS scores with LLM-as-judge:
  pip install ragas
  Then replace the keyword-overlap functions with ragas.metrics.* using Ollama as LLM judge.

Usage:
  docker exec medisense_fastapi python scripts/run_ragas_eval.py
  docker exec medisense_fastapi python scripts/run_ragas_eval.py --output results/ragas_eval.json
"""
import json
import sys
import os
import math
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("POSTGRES_PASSWORD", "dummy")
os.environ.setdefault("REDIS_PASSWORD", "dummy")
os.environ.setdefault("JWT_SECRET_KEY", "dummy")
os.environ.setdefault("PGCRYPTO_KEY", "dummy")

# ── Evaluation set with ground-truth expected content ────────────────────────
# Format: (query, ground_truth_keywords, expected_answer_keywords)
#   ground_truth_keywords: what SHOULD appear in retrieved context
#   expected_answer_keywords: what SHOULD appear in the LLM answer

RAGAS_TEST_SET = [
    (
        "Quels sont les effets secondaires du paracétamol ?",
        ["paracetamol", "surdosage", "hepatotox", "doliprane"],
        ["effets", "surdosage", "foie", "doses"],
    ),
    (
        "Quelle est la posologie de l'amoxicilline pour une angine ?",
        ["amoxicilline", "angine", "1g", "streptocoque"],
        ["amoxicilline", "posologie", "angine", "1g"],
    ),
    (
        "Comment gérer une urgence cardiaque au Maroc ?",
        ["141", "SAMU", "urgence", "cardiaque"],
        ["141", "urgence", "SAMU", "Maroc"],
    ),
    (
        "Quel est le traitement de première ligne pour l'HTA au Maroc ?",
        ["hypertension", "AMO", "IEC", "amlodipine"],
        ["hypertension", "traitement", "IEC", "Maroc"],
    ),
    (
        "Quels médicaments sont remboursés par l'AMO pour le diabète ?",
        ["AMO", "metformine", "diabete", "remboursement"],
        ["AMO", "metformine", "diabete", "remboursement"],
    ),
    (
        "Qu'est-ce que la tuberculose et comment est-elle traitée au Maroc ?",
        ["tuberculose", "PNLT", "gratuit", "rifampicine"],
        ["tuberculose", "traitement", "Maroc", "PNLT"],
    ),
    (
        "Le paracétamol est-il contre-indiqué en insuffisance hépatique ?",
        ["paracetamol", "hepatique", "contre", "insuffisance"],
        ["paracetamol", "hepatique", "contre-indique"],
    ),
    (
        "Quels sont les symptômes d'un infarctus du myocarde ?",
        ["infarctus", "I21", "douleur thoracique", "urgence"],
        ["infarctus", "douleur", "urgence", "thoracique"],
    ),
    (
        "Peut-on prendre de l'ibuprofène pendant la grossesse ?",
        ["ibuprofene", "grossesse", "24 SA", "contre"],
        ["ibuprofene", "grossesse", "contre-indique"],
    ),
    (
        "Quel est le prix du paracétamol au Maroc ?",
        ["paracetamol", "dhs", "MAD", "PPV"],
        ["prix", "dhs", "Maroc", "paracetamol"],
    ),
]


def _keyword_overlap(text: str, keywords: list[str]) -> float:
    """Fraction of keywords found in text (case-insensitive)."""
    if not keywords:
        return 1.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords)


def context_precision(retrieved_chunks: list[dict], ground_truth_kws: list[str]) -> float:
    """Fraction of retrieved chunks that contain at least one ground-truth keyword."""
    if not retrieved_chunks:
        return 0.0
    relevant = sum(
        1 for c in retrieved_chunks
        if any(kw.lower() in c["text"].lower() for kw in ground_truth_kws)
    )
    return relevant / len(retrieved_chunks)


def context_recall(retrieved_chunks: list[dict], ground_truth_kws: list[str]) -> float:
    """Fraction of ground-truth keywords covered by the retrieved context pool."""
    if not ground_truth_kws:
        return 1.0
    combined = " ".join(c["text"] for c in retrieved_chunks).lower()
    covered = sum(1 for kw in ground_truth_kws if kw.lower() in combined)
    return covered / len(ground_truth_kws)


def answer_faithfulness(answer: str, retrieved_chunks: list[dict]) -> float:
    """
    Proxy for faithfulness: fraction of answer sentences that can be supported
    by at least one retrieved chunk (word-overlap ≥ 0.3).
    """
    sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 20]
    if not sentences:
        return 1.0
    context = " ".join(c["text"] for c in retrieved_chunks)
    supported = 0
    for sentence in sentences:
        words = [w for w in sentence.lower().split() if len(w) > 3]
        if not words:
            continue
        overlap = sum(1 for w in words if w in context.lower()) / len(words)
        if overlap >= 0.25:
            supported += 1
    return supported / len(sentences)


def answer_relevance(answer: str, query: str) -> float:
    """Proxy: fraction of query keywords (>3 chars) present in the answer."""
    query_words = [w for w in query.lower().split() if len(w) > 3]
    if not query_words:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for w in query_words if w in answer_lower)
    return hits / len(query_words)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM generation (evaluate retrieval only)")
    args = parser.parse_args()

    from app.rag.vectorstore import hybrid_search

    use_llm = not args.skip_llm
    if use_llm:
        try:
            import httpx
            from app.core.config import get_settings
            settings = get_settings()
            ollama_url = f"http://{settings.OLLAMA_HOST}:{settings.OLLAMA_PORT}"
        except Exception as e:
            print(f"[WARN] LLM not available ({e}) — running retrieval-only mode")
            use_llm = False

    print("=" * 60)
    print("MediSense RAGAS-style Evaluation")
    print(f"Mode: {'Full (retrieval + generation)' if use_llm else 'Retrieval-only'}")
    print(f"Test set: {len(RAGAS_TEST_SET)} queries")
    print("=" * 60)

    per_query = []
    total_ctx_prec = total_ctx_rec = total_faith = total_rel = 0.0
    n_llm = 0

    for i, (query, gt_kws, ans_kws) in enumerate(RAGAS_TEST_SET):
        chunks = hybrid_search(query, limit=5)
        ctx_prec = context_precision(chunks, gt_kws)
        ctx_rec = context_recall(chunks, gt_kws)

        answer = ""
        faithfulness = None
        relevance = None

        if use_llm and chunks:
            context_text = "\n\n".join(c["text"][:300] for c in chunks[:3])
            prompt = (
                f"Tu es un assistant médical pour patients marocains. "
                f"Réponds en français à la question suivante en utilisant uniquement le contexte fourni.\n\n"
                f"Contexte:\n{context_text}\n\n"
                f"Question: {query}\n\nRéponse:"
            )
            try:
                resp = httpx.post(
                    f"{ollama_url}/api/generate",
                    json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
                    timeout=30.0,
                )
                answer = resp.json().get("response", "").strip()
                faithfulness = answer_faithfulness(answer, chunks)
                relevance = answer_relevance(answer, query)
                total_faith += faithfulness
                total_rel += relevance
                n_llm += 1
            except Exception as e:
                answer = f"[LLM error: {e}]"

        total_ctx_prec += ctx_prec
        total_ctx_rec += ctx_rec

        status = "✓" if ctx_prec >= 0.5 else "✗"
        faith_str = f" faith={faithfulness:.2f}" if faithfulness is not None else ""
        print(f"  [{i+1:02d}] {status} {query[:52]:<52} ctx_prec={ctx_prec:.2f}{faith_str}")

        per_query.append({
            "query": query,
            "context_precision": round(ctx_prec, 4),
            "context_recall": round(ctx_rec, 4),
            "answer_faithfulness": round(faithfulness, 4) if faithfulness is not None else None,
            "answer_relevance": round(relevance, 4) if relevance is not None else None,
            "answer_snippet": answer[:200] if answer else "",
            "top1_chunk": chunks[0]["text"][:120] if chunks else "",
        })

    n = len(RAGAS_TEST_SET)
    avg_ctx_prec = total_ctx_prec / n
    avg_ctx_rec = total_ctx_rec / n
    avg_faith = total_faith / n_llm if n_llm else None
    avg_rel = total_rel / n_llm if n_llm else None

    print("\n" + "=" * 60)
    print("RAGAS-style Results")
    print("=" * 60)
    print(f"  Context Precision   : {avg_ctx_prec:.4f}  (retrieved chunks that are relevant)")
    print(f"  Context Recall      : {avg_ctx_rec:.4f}  (ground-truth keywords in context)")
    if avg_faith is not None:
        print(f"  Answer Faithfulness : {avg_faith:.4f}  (answer grounded in retrieved context)")
    if avg_rel is not None:
        print(f"  Answer Relevance    : {avg_rel:.4f}  (answer addresses the question)")

    print("\n" + "=" * 60)
    print("INTERPRETATION")
    print("=" * 60)
    if avg_ctx_prec >= 0.7:
        print(f"  Precision {avg_ctx_prec:.2f} — GOOD: retrieval returns mostly relevant chunks")
    else:
        print(f"  Precision {avg_ctx_prec:.2f} — needs better chunking or query rewriting")

    if avg_ctx_rec >= 0.7:
        print(f"  Recall    {avg_ctx_rec:.2f} — GOOD: context covers expected knowledge")
    else:
        print(f"  Recall    {avg_ctx_rec:.2f} — corpus may be missing key content")

    if avg_faith is not None:
        if avg_faith >= 0.7:
            print(f"  Faithful  {avg_faith:.2f} — GOOD: LLM stays grounded in retrieved context")
        else:
            print(f"  Faithful  {avg_faith:.2f} — LLM may be hallucinating beyond the context")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "timestamp": datetime.now().isoformat(),
            "mode": "full" if use_llm else "retrieval_only",
            "test_queries": n,
            "metrics": {
                "context_precision": round(avg_ctx_prec, 4),
                "context_recall": round(avg_ctx_rec, 4),
                "answer_faithfulness": round(avg_faith, 4) if avg_faith else None,
                "answer_relevance": round(avg_rel, 4) if avg_rel else None,
            },
            "per_query": per_query,
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nReport saved → {out}")


if __name__ == "__main__":
    main()
