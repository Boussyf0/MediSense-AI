#!/usr/bin/env python3
"""
RAG Evaluation Pipeline — MRR, NDCG@5, RRF vs Cross-Encoder comparison.

Runs a test set of 30 medical queries against the Qdrant corpus and computes:
  - MRR@10    (Mean Reciprocal Rank)
  - NDCG@5    (Normalized Discounted Cumulative Gain)
  - Precision@3
  - RRF rank correlation vs cross-encoder reranking
  - Top-3 overlap between RRF and cross-encoder

Usage:
  cd backend
  python scripts/run_evaluation.py
  python scripts/run_evaluation.py --output results/eval_sprint3.json
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

# ── Ground truth test set ─────────────────────────────────────────────────────
# Format: (query, [expected_relevant_keywords_in_result_text])
# A result is considered relevant if ANY keyword appears in the chunk text.

TEST_SET = [
    # Drug queries
    ("effets secondaires paracétamol", ["paracetamol", "doliprane", "hepatotox", "surdosage"]),
    ("contre-indications ibuprofène grossesse", ["ibuprofene", "grossesse", "24 SA", "contre"]),
    ("posologie amoxicilline angine adulte", ["amoxicilline", "angine", "1g", "streptocoque"]),
    ("interactions médicamenteuses metformine alcool", ["metformine", "alcool", "acidose"]),
    ("surdosage paracétamol antidote", ["paracetamol", "n-acetylcysteine", "surdosage", "urgence"]),
    ("oméprazole reflux gastrique posologie", ["omeprazole", "reflux", "IPP", "20mg"]),
    ("levothyroxine hypothyroïdie prise à jeun", ["levothyroxine", "thyroide", "jeun", "TSH"]),
    ("salbutamol crise asthme utilisation", ["salbutamol", "asthme", "crise", "bouffee"]),

    # Disease queries
    ("symptômes infarctus du myocarde urgence", ["infarctus", "I21", "douleur thoracique", "SAMU"]),
    ("traitement hypertension artérielle", ["hypertension", "I10", "IEC", "140/90"]),
    ("diabète type 2 HbA1c objectif", ["diabete", "E11", "HbA1c", "7%", "metformine"]),
    ("symptômes migraine traitement", ["migraine", "G43", "triptan", "pulsatile"]),
    ("pneumonie antibiotique traitement", ["pneumonie", "J18", "amoxicilline", "radiographie"]),
    ("asthme traitement de fond corticoïdes", ["asthme", "J45", "CSI", "corticoide", "SABA"]),
    ("AVC ischémique urgence thrombolyse", ["AVC", "I63", "thrombolyse", "urgence", "15"]),
    ("lombalgie imagerie recommandation", ["lombalgie", "M54", "imagerie", "6 semaines"]),

    # Symptom queries
    ("j'ai de la fièvre 39 degrés que faire", ["fievre", "R50", "temperature", "infection"]),
    ("douleur abdominale droite appendicite", ["douleur", "R10", "abdominale", "appendicite"]),
    ("toux chronique 3 mois causes", ["toux", "R05", "chronique", "asthme", "RGO"]),
    ("céphalée brutale hémorragie méningée", ["cephalee", "R51", "hemorragie", "urgence", "scanner"]),
    ("dyspnée essoufflement insuffisance cardiaque", ["dyspnee", "insuffisance cardiaque", "I50"]),

    # Guideline queries
    ("recommandation HAS hypertension bilan initial", ["hypertension", "bilan", "glycemie", "ECG"]),
    ("stratégie diabète type 2 étapes traitement", ["diabete", "metformine", "etape", "HbA1c"]),
    ("antibiothérapie rhinopharyngite recommandation", ["rhinopharyngite", "antibiotique", "viral"]),
    ("dépistage cancer sein mammographie", ["cancer", "sein", "mammographie", "50", "74"]),

    # Complex/mixed queries
    ("ibuprofène contre-indiqué asthme AINS", ["ibuprofene", "asthme", "AINS", "contre"]),
    ("paracétamol insuffisance rénale dosage", ["paracetamol", "renale", "insuffisance"]),
    ("prévention AVC aspirine statine", ["AVC", "aspirine", "statine", "prevention"]),
    ("vaccin grippe personnes âgées recommandation", ["vaccin", "grippe", "65", "annuel"]),
    ("obésité IMC chirurgie bariatrique critères", ["obesite", "IMC", "chirurgie", "bariatrique"]),
]


def _is_relevant(chunk_text: str, keywords: list[str]) -> bool:
    text_lower = chunk_text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def compute_mrr(results_per_query: list[list[tuple[str, bool]]]) -> float:
    """Mean Reciprocal Rank @ 10."""
    rr_sum = 0.0
    for results in results_per_query:
        for rank, (_, relevant) in enumerate(results[:10], start=1):
            if relevant:
                rr_sum += 1.0 / rank
                break
    return rr_sum / len(results_per_query)


def compute_ndcg(results_per_query: list[list[tuple[str, bool]]], k: int = 5) -> float:
    """Normalized Discounted Cumulative Gain @ k."""
    ndcg_sum = 0.0
    for results in results_per_query:
        dcg = sum(
            1.0 / math.log2(rank + 1)
            for rank, (_, relevant) in enumerate(results[:k], start=1)
            if relevant
        )
        # Ideal DCG: all relevant at top
        n_relevant = sum(1 for _, relevant in results[:k] if relevant)
        ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, n_relevant + 1))
        ndcg_sum += (dcg / ideal_dcg) if ideal_dcg > 0 else 0.0
    return ndcg_sum / len(results_per_query)


def compute_precision_at_k(results_per_query: list[list[tuple[str, bool]]], k: int = 3) -> float:
    """Precision @ k."""
    p_sum = 0.0
    for results in results_per_query:
        relevant = sum(1 for _, rel in results[:k] if rel)
        p_sum += relevant / k
    return p_sum / len(results_per_query)


def main():
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument("--output", type=str, default=None, help="Save results to JSON file")
    parser.add_argument("--reranker", action="store_true", help="Also run cross-encoder reranker comparison")
    args = parser.parse_args()

    from app.rag.vectorstore import hybrid_search

    print("=" * 60)
    print("MediSense RAG Evaluation")
    print(f"Test set: {len(TEST_SET)} queries")
    print("=" * 60)

    rrf_results_per_query = []
    query_details = []

    for i, (query, relevant_keywords) in enumerate(TEST_SET):
        results = hybrid_search(query, limit=10)
        ranked = [(r["text"], _is_relevant(r["text"], relevant_keywords)) for r in results]
        rrf_results_per_query.append(ranked)

        top1_relevant = ranked[0][1] if ranked else False
        query_details.append({
            "query": query,
            "top1_relevant": top1_relevant,
            "top3_relevant_count": sum(1 for _, rel in ranked[:3] if rel),
            "top1_text_snippet": results[0]["text"][:80] if results else "",
            "top1_score": results[0]["score"] if results else 0.0,
        })

        status = "✓" if top1_relevant else "✗"
        score = results[0]["score"] if results else 0.0
        print(f"  [{i+1:02d}] {status} {query[:50]:<50} score={score:.3f}")

    # Metrics
    mrr = compute_mrr(rrf_results_per_query)
    ndcg5 = compute_ndcg(rrf_results_per_query, k=5)
    p3 = compute_precision_at_k(rrf_results_per_query, k=3)
    top1_acc = sum(1 for d in query_details if d["top1_relevant"]) / len(query_details)

    print("\n" + "=" * 60)
    print("RESULTS — RRF (Dense + BM25)")
    print("=" * 60)
    print(f"  MRR@10        : {mrr:.4f}")
    print(f"  NDCG@5        : {ndcg5:.4f}")
    print(f"  Precision@3   : {p3:.4f}")
    print(f"  Top-1 Accuracy: {top1_acc:.4f} ({sum(1 for d in query_details if d['top1_relevant'])}/{len(query_details)})")

    # Cross-encoder comparison
    reranker_metrics = None
    if args.reranker:
        try:
            from app.rag.reranker import evaluate_rrf_vs_crossencoder
            print("\n[Reranker] Running RRF vs Cross-Encoder comparison...")
            queries = [q for q, _ in TEST_SET]
            reranker_metrics = evaluate_rrf_vs_crossencoder(queries, top_k=10)
            print(f"\nRRF vs Cross-Encoder:")
            print(f"  Rank correlation : {reranker_metrics.get('rank_correlation', 0):.4f}")
            print(f"  Top-3 overlap    : {reranker_metrics.get('top3_overlap', 0):.4f}")
            print(f"  MRR (reranked)   : {reranker_metrics.get('mrr_rrf', 0):.4f}")
        except Exception as e:
            print(f"  [WARN] Reranker evaluation failed: {e}")

    # Interpretation
    print("\n" + "=" * 60)
    print("INTERPRETATION")
    print("=" * 60)
    if mrr >= 0.7:
        print(f"  MRR {mrr:.2f} — GOOD: relevant result usually in top 2")
    elif mrr >= 0.5:
        print(f"  MRR {mrr:.2f} — ACCEPTABLE: relevant result in top 3-4")
    else:
        print(f"  MRR {mrr:.2f} — NEEDS IMPROVEMENT: expand corpus or tune chunking")

    if ndcg5 >= 0.7:
        print(f"  NDCG@5 {ndcg5:.2f} — GOOD: top-5 results are highly relevant")
    elif ndcg5 >= 0.5:
        print(f"  NDCG@5 {ndcg5:.2f} — ACCEPTABLE: some irrelevant results in top-5")
    else:
        print(f"  NDCG@5 {ndcg5:.2f} — LOW: corpus too small or queries out of domain")

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "timestamp": datetime.now().isoformat(),
            "corpus_size": "see Qdrant dashboard",
            "metrics": {
                "mrr_at_10": round(mrr, 4),
                "ndcg_at_5": round(ndcg5, 4),
                "precision_at_3": round(p3, 4),
                "top1_accuracy": round(top1_acc, 4),
            },
            "reranker": reranker_metrics,
            "per_query": query_details,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nFull report saved → {output_path}")


if __name__ == "__main__":
    main()
