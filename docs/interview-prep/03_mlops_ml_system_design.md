# 03 — MLOps & ML System Design

> This is where your MediSense **deployment** experience makes you stand out — most candidates
> have never shipped a model. You debugged a real production cascade. Use it.

---

## PART A — MLOps

### The production ML lifecycle
```
Data → Features → Train → Evaluate → Register → Deploy → Serve → Monitor → (Retrain) ↺
```
Most candidates stop at "Evaluate." The job is everything after.

### Key concepts
- **Experiment tracking** — log params/metrics/artifacts per run (MLflow, W&B). Reproducibility.
- **Model registry** — versioned models with stages (staging/production) + promotion gates (e.g., AUC/F1 thresholds — you have this in MediSense via MLflow).
- **CI/CD for ML** — test data + code + model; automate retrain → eval → deploy. (You used GitHub Actions + a coverage-gated pre-push hook.)
- **Feature store** — consistent features between training & serving → prevents **training/serving skew**.
- **Reproducibility** — pin data versions, seeds, environments (Docker).

### Serving patterns
- **Batch** — precompute predictions on a schedule (recommendations overnight). Cheap, not fresh.
- **Online / real-time** — synchronous API per request (your FastAPI endpoints). Needs low latency.
- **Streaming** — react to events (your Kafka IoT vitals pipeline).
- Trade-offs: latency vs throughput vs cost. Optimize with batching, caching, quantization, smaller/distilled models, GPU.

### Monitoring (what breaks in prod)
- **Data drift** — input distribution changes (new patient demographics). Detect: PSI, KL divergence, KS test.
- **Concept drift** — relationship X→y changes (post-COVID no-show behavior). Detect: live metric decay.
- **Operational** — latency, error rate, throughput, **memory** (you hit OOM — right-sizing is a real MLOps skill), cost.
- **Data quality** — schema/nulls/range checks.
- Response: alert → investigate → retrain / rollback. Keep a fallback model.

> One-liner: "Models decay silently — the failure isn't a 500, it's slowly worse predictions. So I monitor live metrics + input drift, not just uptime."

### LLM-specific Ops (LLMOps)
- Eval suites (faithfulness, regression tests on prompts), prompt versioning, cost/token monitoring, latency, guardrails, caching, fallback models, PII redaction.

---

## PART B — ML System Design (a repeatable framework)

When asked "Design X," **don't jump to the model.** Use this structure out loud:

### The framework (memorize the 7 steps)
1. **Clarify requirements** — functional (what predict?) + non-functional (scale, latency, freshness, budget). Ask questions.
2. **Frame as ML** — what's the target? classification/ranking/regression? What's "good"? Online vs batch?
3. **Data** — sources, labels (how obtained?), volume, leakage risks, bias.
4. **Features** — engineering, feature store, real-time vs batch features.
5. **Model** — baseline first (logistic/tree), then iterate (XGBoost, NN). Justify trade-offs (accuracy vs latency vs interpretability).
6. **Evaluation** — offline metric (tie to business), then **online A/B test** with a guardrail metric.
7. **Serve & monitor** — deployment pattern, latency budget, drift monitoring, retraining cadence, fallback.

> Always: start simple (baseline), state assumptions, discuss trade-offs, mention monitoring. Interviewers grade *structure & trade-off reasoning*, not the "right" answer.

### Worked example 1 — "Design a RAG medical chatbot" (your home turf)
- **Clarify:** languages? source corpus? latency? must cite? safety/abstain?
- **Data:** medical documents → chunk + embed → vector DB.
- **Retrieval:** hybrid (dense + BM25) → rerank top-k.
- **Generation:** LLM grounded in context, cite sources, abstain if low confidence.
- **Eval:** retrieval recall@k + generation faithfulness (RAGAS/human); safety red-teaming.
- **Serve:** async API, cache frequent queries, stream tokens; PII handling.
- **Monitor:** hallucination rate, retrieval hit rate, latency, cost/query, user feedback loop.
- **Safety:** disclaimers, no diagnosis claims, escalate emergencies. ← shows maturity.

### Worked example 2 — "Design appointment no-show prediction" (you built this)
- **Frame:** binary classification, output probability; batch scoring before appointment day.
- **Features:** patient history (prior no-shows), lead time, day/time, weather, distance, reminders sent.
- **Imbalance:** PR-AUC, class weights / SMOTE.
- **Model:** XGBoost baseline (tabular). Calibrate probabilities.
- **Action:** high-risk → SMS reminders / overbooking (close the ML→business loop).
- **Eval:** PR-AUC offline; online — did no-show rate drop? (A/B).
- **Monitor:** concept drift (behavior changes), feedback labels for retraining (your MLflow loop).

### Worked example 3 — "Design a recommendation system" (classic)
- Candidate generation (retrieval, collaborative filtering / two-tower) → ranking (gradient-boosted / NN) → re-ranking (diversity, business rules).
- Cold start (content-based for new users/items), feedback loop, online A/B.

---

## PART C — Tie it to MediSense (your differentiator)

You can speak from real experience on:
- **Containerized deployment** (Docker) of an ML-bearing API on a cloud platform (Fly.io).
- **Right-sizing compute** — you diagnosed OOM kills from ML library memory and scaled (512MB→2GB). Most candidates have never reasoned about model memory in prod.
- **Schema/data infra** — Postgres + Redis, migrations, encrypted PII, seeding.
- **CI/CD + quality gates** — GitHub Actions, 80% coverage pre-push gate, integration tests on real DBs.
- **Graceful degradation** — non-blocking startup for optional services (Qdrant/LLM), so the API stays up when a dependency is down. ← strong reliability signal.

> Power statement: "I've felt the gap between a notebook model and a service that stays up — memory limits, cold starts, dependency failures, drift. That production scar tissue is what I bring."
