#!/usr/bin/env python3
"""
Benchmark end-user latency of the configured LLM provider.

Measures:
  - end-to-first-token (stream)
  - end-to-done (stream)
  - retrieval_and_mcp timing from pipeline done event
  - generation timing from pipeline done event

Usage:
  docker exec medisense_fastapi python scripts/benchmark_llm_provider.py --output results/llm_provider_benchmark.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("POSTGRES_PASSWORD", "dummy")
os.environ.setdefault("REDIS_PASSWORD", "dummy")
os.environ.setdefault("JWT_SECRET_KEY", "dummy")
os.environ.setdefault("PGCRYPTO_KEY", "dummy")


SAMPLE_QUERIES = [
    "Quels sont les effets secondaires du paracetamol ?",
    "J'ai une douleur thoracique et je transpire beaucoup.",
    "Quelle est la prise en charge initiale de l'hypertension ?",
    "Quels examens demander pour une fatigue persistante ?",
    "Interaction entre warfarine et ibuprofene ?",
    "Symptomes frequents du diabete type 2 ?",
    "Conduite a tenir devant une dyspnee brutale ?",
    "Que faire en cas de fievre chez un enfant ?",
    "Risque de surdosage au paracetamol ?",
    "Conseils pour une lombalgie aigue ?",
]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (p / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


async def _bench_one(query: str) -> dict:
    from app.rag.pipeline import run_stream

    last_error = None
    for attempt in range(1, 4):
        started = time.perf_counter()
        first_token_ms = None
        done_timings = {}
        token_count = 0

        try:
            async for event in run_stream(query):
                event_type = event.get("type")
                if event_type == "token":
                    token_count += 1
                    if first_token_ms is None:
                        first_token_ms = (time.perf_counter() - started) * 1000
                elif event_type == "done":
                    done_timings = event.get("timings_ms", {}) or {}
                    break

            total_ms = (time.perf_counter() - started) * 1000
            return {
                "query": query,
                "status": "ok",
                "attempts": attempt,
                "first_token_ms": round(first_token_ms or total_ms, 2),
                "total_stream_ms": round(total_ms, 2),
                "retrieval_and_mcp_ms": round(float(done_timings.get("retrieval_and_mcp", 0.0)), 2),
                "generation_ms": round(float(done_timings.get("generation", 0.0)), 2),
                "token_events": token_count,
            }
        except Exception as exc:
            last_error = str(exc)
            # Basic backoff for transient provider throttling (e.g., 429).
            await asyncio.sleep(2 ** attempt)

    return {
        "query": query,
        "status": "error",
        "attempts": 3,
        "error": last_error or "unknown error",
    }


async def _run(sample_size: int, warmup: bool) -> dict:
    from app.core.config import get_settings

    settings = get_settings()
    queries = SAMPLE_QUERIES[: max(1, min(sample_size, len(SAMPLE_QUERIES)))]

    if warmup:
        warm = await _bench_one(queries[0])
        if warm.get("status") == "ok":
            print(
                "[warmup] "
                f"first_token={warm['first_token_ms']:.2f}ms "
                f"total={warm['total_stream_ms']:.2f}ms"
            )
        else:
            print(f"[warmup] error={warm.get('error')}")

    rows = []
    for idx, query in enumerate(queries, start=1):
        row = await _bench_one(query)
        rows.append(row)
        if row.get("status") == "ok":
            print(
                f"[{idx:02d}/{len(queries):02d}] "
                f"first_token={row['first_token_ms']:.2f}ms "
                f"total={row['total_stream_ms']:.2f}ms "
                f"retrieval={row['retrieval_and_mcp_ms']:.2f}ms"
            )
        else:
            print(f"[{idx:02d}/{len(queries):02d}] error={row.get('error')}")

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    first_tokens = [r["first_token_ms"] for r in ok_rows]
    totals = [r["total_stream_ms"] for r in ok_rows]
    retrievals = [r["retrieval_and_mcp_ms"] for r in ok_rows if r["retrieval_and_mcp_ms"] > 0]
    generations = [r["generation_ms"] for r in ok_rows if r["generation_ms"] > 0]

    return {
        "timestamp": datetime.now().isoformat(),
        "provider": settings.LLM_PROVIDER,
        "provider_model": settings.GROQ_MODEL if settings.LLM_PROVIDER.lower() == "groq" else settings.OLLAMA_MODEL,
        "samples": len(rows),
        "successful_samples": len(ok_rows),
        "failed_samples": len(rows) - len(ok_rows),
        "metrics_ms": {
            "first_token": {
                "p50": round(_percentile(first_tokens, 50), 2),
                "p95": round(_percentile(first_tokens, 95), 2),
                "mean": round(statistics.mean(first_tokens), 2) if first_tokens else 0.0,
            },
            "total_stream": {
                "p50": round(_percentile(totals, 50), 2),
                "p95": round(_percentile(totals, 95), 2),
                "mean": round(statistics.mean(totals), 2) if totals else 0.0,
            },
            "retrieval_and_mcp": {
                "p50": round(_percentile(retrievals, 50), 2) if retrievals else 0.0,
                "p95": round(_percentile(retrievals, 95), 2) if retrievals else 0.0,
                "mean": round(statistics.mean(retrievals), 2) if retrievals else 0.0,
            },
            "generation": {
                "p50": round(_percentile(generations, 50), 2) if generations else 0.0,
                "p95": round(_percentile(generations, 95), 2) if generations else 0.0,
                "mean": round(statistics.mean(generations), 2) if generations else 0.0,
            },
        },
        "per_query": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark LLM provider latency")
    parser.add_argument("--sample", type=int, default=10, help="Number of sample queries (max 10)")
    parser.add_argument("--no-warmup", action="store_true", help="Disable warmup query before measurement")
    parser.add_argument("--output", type=str, default=None, help="Write JSON report")
    args = parser.parse_args()

    report = asyncio.run(_run(args.sample, warmup=not args.no_warmup))

    print("\n=== LLM Provider Benchmark ===")
    print(f"Provider : {report['provider']}")
    print(f"Model    : {report['provider_model']}")
    print(f"Samples  : {report['samples']}")
    print(f"First token p95 : {report['metrics_ms']['first_token']['p95']:.2f} ms")
    print(f"Total p95       : {report['metrics_ms']['total_stream']['p95']:.2f} ms")
    print(f"Retrieval p95   : {report['metrics_ms']['retrieval_and_mcp']['p95']:.2f} ms")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"Saved report → {output_path}")


if __name__ == "__main__":
    main()
