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
import asyncio
import time
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
    # ── Drug queries (standard) ───────────────────────────────────────────────
    ("effets secondaires paracétamol", ["paracetamol", "doliprane", "hepatotox", "surdosage"]),
    ("contre-indications ibuprofène grossesse", ["ibuprofene", "grossesse", "24 SA", "contre"]),
    ("posologie amoxicilline angine adulte", ["amoxicilline", "angine", "1g", "streptocoque"]),
    ("interactions médicamenteuses metformine alcool", ["metformine", "alcool", "acidose"]),
    ("surdosage paracétamol antidote", ["paracetamol", "n-acetylcysteine", "surdosage", "urgence"]),
    ("oméprazole reflux gastrique posologie", ["omeprazole", "reflux", "IPP", "20mg"]),
    ("levothyroxine hypothyroïdie prise à jeun", ["levothyroxine", "thyroide", "jeun", "TSH"]),
    ("salbutamol crise asthme utilisation", ["salbutamol", "asthme", "crise", "bouffee"]),
    ("metformine effets secondaires digestifs", ["metformine", "digestif", "nausee", "diarrhee"]),
    ("warfarine surveillance INR saignement", ["warfarine", "INR", "saignement", "anticoagulant"]),
    ("amoxicilline allergie pénicilline", ["amoxicilline", "allergie", "penicilline", "contre"]),
    ("atorvastatine douleurs musculaires myopathie", ["atorvastatine", "statine", "myopathie", "muscle"]),

    # ── Disease queries ───────────────────────────────────────────────────────
    ("symptômes infarctus du myocarde urgence", ["infarctus", "I21", "douleur thoracique", "SAMU"]),
    ("traitement hypertension artérielle", ["hypertension", "I10", "IEC", "140/90"]),
    ("diabète type 2 HbA1c objectif", ["diabete", "E11", "HbA1c", "7%", "metformine"]),
    ("symptômes migraine traitement", ["migraine", "G43", "triptan", "pulsatile"]),
    ("pneumonie antibiotique traitement", ["pneumonie", "J18", "amoxicilline", "radiographie"]),
    ("asthme traitement de fond corticoïdes", ["asthme", "J45", "CSI", "corticoide", "SABA"]),
    ("AVC ischémique urgence thrombolyse", ["AVC", "I63", "thrombolyse", "urgence"]),
    ("lombalgie imagerie recommandation", ["lombalgie", "M54", "imagerie", "6 semaines"]),
    ("insuffisance rénale chronique stades", ["renale", "N18", "chronique", "stade"]),
    ("fibrillation auriculaire anticoagulation", ["fibrillation", "I48", "anticoagulant", "AVC"]),
    ("dépression traitement antidépresseurs", ["depression", "F32", "sertraline", "ISRS"]),
    ("épilepsie traitement antiépileptiques", ["epilepsie", "G40", "valproate", "carbamazepine"]),

    # ── Symptom queries ───────────────────────────────────────────────────────
    ("j'ai de la fièvre 39 degrés que faire", ["fievre", "R50", "temperature", "infection"]),
    ("douleur abdominale droite appendicite", ["douleur", "R10", "abdominale", "appendicite"]),
    ("toux chronique 3 mois causes", ["toux", "R05", "chronique", "asthme", "RGO"]),
    ("céphalée brutale hémorragie méningée", ["cephalee", "R51", "hemorragie", "urgence", "scanner"]),
    ("dyspnée essoufflement insuffisance cardiaque", ["dyspnee", "insuffisance cardiaque", "I50"]),
    ("palpitations cardiaques tachycardie", ["palpitation", "R00", "tachycardie", "cardiaque"]),
    ("oedème membres inférieurs causes", ["oedeme", "R60", "membres", "cardiaque", "renale"]),
    ("perte de poids inexpliquée cancer", ["perte", "R64", "poids", "amaigrissement", "cancer"]),

    # ── Guideline queries ─────────────────────────────────────────────────────
    ("recommandation HAS hypertension bilan initial", ["hypertension", "bilan", "glycemie", "ECG"]),
    ("stratégie diabète type 2 étapes traitement", ["diabete", "metformine", "etape", "HbA1c"]),
    ("antibiothérapie rhinopharyngite recommandation", ["rhinopharyngite", "antibiotique", "viral"]),
    ("dépistage cancer sein mammographie", ["cancer", "sein", "mammographie", "50", "74"]),
    ("prévention cardiovasculaire facteurs de risque", ["cardiovasculaire", "risque", "tabac", "cholesterol"]),
    ("grossesse diabète gestationnel surveillance", ["grossesse", "diabete", "gestationnel", "glycemie"]),

    # ── Moroccan context queries ──────────────────────────────────────────────
    ("numéro urgence médicale Maroc SAMU", ["141", "SAMU", "urgence", "Maroc"]),
    ("hypertension traitement AMO Maroc remboursé", ["hypertension", "AMO", "Maroc", "141"]),
    ("diabète médicaments remboursés AMO Maroc", ["diabete", "AMO", "metformine", "remboursement"]),
    ("tuberculose traitement gratuit Maroc PNLT", ["tuberculose", "PNLT", "gratuit", "Maroc"]),
    ("assurance maladie RAMED Maroc pauvre", ["RAMED", "AMO", "Maroc", "assurance"]),
    ("paludisme traitement Maroc chloroquine", ["paludisme", "chloroquine", "Maroc", "artemether"]),
    ("vaccins obligatoires Maroc enfants PNI", ["vaccin", "PNI", "Maroc", "obligatoire"]),
    ("hôpital urgence Casablanca Rabat Maroc", ["141", "CHU", "Maroc", "urgence"]),
    ("cancer Maroc incidence mortalité traitement", ["cancer", "Maroc", "incidence", "traitement"]),
    ("VIH ARV gratuit Maroc PNLS", ["VIH", "ARV", "gratuit", "Maroc", "PNLS"]),
    ("antibiotiques résistance Maroc rhinopharyngite", ["antibiotique", "resistance", "Maroc", "viral"]),
    ("santé maternelle accouchement Maroc maternite", ["maternelle", "Maroc", "accouchement", "maternite"]),

    # ── Moroccan drug price queries (new — DMP data) ──────────────────────────
    ("prix paracétamol Maroc dhs MAD pharmacie", ["paracetamol", "dhs", "Maroc", "MAD", "PPV"]),
    ("prix amoxicilline Maroc dirham", ["amoxicilline", "dhs", "Maroc", "MAD", "PPV"]),
    ("médicament générique moins cher Maroc", ["generique", "Maroc", "moins", "prix"]),
    ("prix metformine Maroc pharmacie", ["metformine", "dhs", "Maroc", "MAD"]),

    # ── Darija / colloquial queries ───────────────────────────────────────────
    ("mal de tête fort douleur tête que faire", ["cephalee", "migraine", "R51", "douleur"]),
    ("je tousse depuis 3 semaines bronchite", ["toux", "bronchite", "J20", "chronique"]),
    ("tension artérielle élevée que faire", ["hypertension", "tension", "I10", "IEC"]),
    ("sucre dans le sang élevé diabète symptômes", ["diabete", "glycemie", "E11", "sucre"]),
    ("mal au ventre diarrhée gastroentérite", ["gastroenterite", "diarrhee", "A09", "abdominale"]),
    ("douleur poitrine essoufflement coeur", ["cardiaque", "I50", "douleur", "thoracique"]),
    ("enfant fièvre 40 degrés convulsions", ["fievre", "convulsion", "R50", "enfant", "pediatrique"]),
    ("grosse fatigue anémie fer sang", ["anemie", "D50", "fer", "fatigue", "hemoglobine"]),

    # ── Complex/mixed queries ─────────────────────────────────────────────────
    ("ibuprofène contre-indiqué asthme AINS", ["ibuprofene", "asthme", "AINS", "contre"]),
    ("paracétamol insuffisance rénale dosage", ["paracetamol", "renale", "insuffisance"]),
    ("prévention AVC aspirine statine", ["AVC", "aspirine", "statine", "prevention"]),
    ("vaccin grippe personnes âgées recommandation", ["vaccin", "grippe", "65", "annuel"]),
    ("obésité IMC chirurgie bariatrique critères", ["obesite", "IMC", "chirurgie", "bariatrique"]),
    ("insuffisance hépatique médicaments contre-indiqués", ["hepatique", "foie", "contre", "insuffisance"]),
    ("polymédication personnes âgées interactions", ["interaction", "medicament", "age", "polymédication"]),
    ("automédication risques Maroc conseil", ["automedication", "risque", "Maroc", "conseil"]),
    ("nutrition obésité alimentation Maroc", ["nutrition", "obesite", "alimentation", "Maroc"]),
    ("santé mentale dépression Maroc stigmatisation", ["mentale", "depression", "Maroc", "sante"]),
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


def _percentile(values: list[float], p: float) -> float:
    """Compute percentile with linear interpolation (p in [0, 100])."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (p / 100.0)
    low = int(math.floor(rank))
    high = int(math.ceil(rank))
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


async def _measure_first_token_latencies(
    queries: list[str],
) -> list[float]:
    """
    Measure end-to-first-token latency (ms) using run_stream().

    Returns one latency value per successful query.
    """
    from app.rag.pipeline import run_stream

    latencies_ms: list[float] = []
    for query in queries:
        started = time.perf_counter()
        try:
            async for event in run_stream(query):
                event_type = event.get("type")
                if event_type == "token":
                    latencies_ms.append((time.perf_counter() - started) * 1000)
                    break
                if event_type == "done":
                    # Safety block / empty token path fallback
                    latencies_ms.append((time.perf_counter() - started) * 1000)
                    break
        except Exception:
            continue
    return latencies_ms


def main():
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument("--output", type=str, default=None, help="Save results to JSON file")
    parser.add_argument("--reranker", action="store_true", help="Also run cross-encoder reranker comparison")
    parser.add_argument(
        "--measure-first-token",
        action="store_true",
        help="Also measure end-to-first-token latency via run_stream()",
    )
    parser.add_argument(
        "--first-token-sample",
        type=int,
        default=20,
        help="How many queries to sample for first-token latency (default: 20)",
    )
    args = parser.parse_args()

    from app.rag.vectorstore import hybrid_search, get_collection_info

    try:
        collection_info = get_collection_info()
        corpus_points = int(collection_info.get("points_count", 0) or 0)
    except Exception:
        collection_info = None
        corpus_points = 0

    print("=" * 60)
    print("MediSense RAG Evaluation")
    print(f"Test set: {len(TEST_SET)} queries")
    if corpus_points:
        print(f"Qdrant points: {corpus_points:,}")
    print("=" * 60)

    rrf_results_per_query = []
    query_details = []
    retrieval_latencies_ms: list[float] = []

    for i, (query, relevant_keywords) in enumerate(TEST_SET):
        t0 = time.perf_counter()
        results = hybrid_search(query, limit=10)
        retrieval_latencies_ms.append((time.perf_counter() - t0) * 1000)
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
    retrieval_p50 = _percentile(retrieval_latencies_ms, 50)
    retrieval_p95 = _percentile(retrieval_latencies_ms, 95)
    retrieval_p99 = _percentile(retrieval_latencies_ms, 99)
    retrieval_mean = sum(retrieval_latencies_ms) / len(retrieval_latencies_ms) if retrieval_latencies_ms else 0.0

    print("\n" + "=" * 60)
    print("RESULTS — RRF (Dense + BM25)")
    print("=" * 60)
    print(f"  MRR@10        : {mrr:.4f}")
    print(f"  NDCG@5        : {ndcg5:.4f}")
    print(f"  Precision@3   : {p3:.4f}")
    print(f"  Top-1 Accuracy: {top1_acc:.4f} ({sum(1 for d in query_details if d['top1_relevant'])}/{len(query_details)})")
    print(f"  Retrieval p50 : {retrieval_p50:.2f} ms")
    print(f"  Retrieval p95 : {retrieval_p95:.2f} ms")
    print(f"  Retrieval p99 : {retrieval_p99:.2f} ms")
    print(f"  Retrieval mean: {retrieval_mean:.2f} ms")

    first_token_metrics = None
    if args.measure_first_token:
        sample_size = max(1, min(args.first_token_sample, len(TEST_SET)))
        sampled_queries = [q for q, _ in TEST_SET[:sample_size]]
        print(f"\n[Latency] Measuring end-to-first-token on {sample_size} queries...")
        first_token_latencies = asyncio.run(_measure_first_token_latencies(sampled_queries))
        if first_token_latencies:
            first_token_metrics = {
                "count": len(first_token_latencies),
                "p50_ms": round(_percentile(first_token_latencies, 50), 2),
                "p95_ms": round(_percentile(first_token_latencies, 95), 2),
                "p99_ms": round(_percentile(first_token_latencies, 99), 2),
                "mean_ms": round(sum(first_token_latencies) / len(first_token_latencies), 2),
            }
            print(f"  First-token p50 : {first_token_metrics['p50_ms']:.2f} ms")
            print(f"  First-token p95 : {first_token_metrics['p95_ms']:.2f} ms")
            print(f"  First-token p99 : {first_token_metrics['p99_ms']:.2f} ms")
            print(f"  First-token mean: {first_token_metrics['mean_ms']:.2f} ms")
        else:
            print("  [WARN] No first-token latency samples collected.")

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
            "corpus_points": corpus_points if corpus_points else "unknown",
            "metrics": {
                "mrr_at_10": round(mrr, 4),
                "ndcg_at_5": round(ndcg5, 4),
                "precision_at_3": round(p3, 4),
                "top1_accuracy": round(top1_acc, 4),
                "retrieval_latency_ms": {
                    "p50": round(retrieval_p50, 2),
                    "p95": round(retrieval_p95, 2),
                    "p99": round(retrieval_p99, 2),
                    "mean": round(retrieval_mean, 2),
                },
            },
            "first_token_latency_ms": first_token_metrics,
            "reranker": reranker_metrics,
            "per_query": query_details,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nFull report saved → {output_path}")


if __name__ == "__main__":
    main()
