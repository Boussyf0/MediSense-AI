# 04 — MediSense AI Project Deep Dive (your #1 interview asset)

> The project deep-dive often decides the loop. You built and *deployed* this — that's rare.
> Rehearse the pitch + anticipate every "why." Concrete, owned answers win.

---

## The 2-minute pitch (memorize the shape, say it naturally)

> "MediSense AI is a healthcare platform for the Moroccan market with two sides: a patient-facing
> AI medical assistant, and a clinic tool for doctors and secretaries.
>
> Technically it's a **RAG system** — a Flutter mobile app talking to an async **FastAPI** backend,
> with an LLM (Llama 3.1 via Groq) grounded on a **Qdrant** vector store for medical Q&A. On top of
> that I built two classical ML services: an **LSTM** that detects anomalies in IoT vitals
> (heart rate, SpO₂, HRV), and an **XGBoost** model that predicts appointment no-shows so the clinic
> can send targeted reminders. Data is privacy-first — patients are pseudonymized and civil identity
> is encrypted in a separate schema, RGPD-aligned.
>
> I took it all the way to production: containerized, deployed on Fly.io with managed Postgres and
> Redis, CI/CD via GitHub Actions, and an 80%-coverage test gate. The hardest part was the
> productionization — I debugged a chain of real deployment failures from logs, from build-context
> bugs to OOM kills under ML inference load."

Tailor the emphasis: GenAI role → lead with RAG. DS role → lead with the LSTM/XGBoost + metrics. MLE role → lead with deployment.

---

## Architecture you must be able to draw
```
Flutter (Android/iOS) ──HTTPS/JWT──► FastAPI (async, Fly.io)
                                       ├── PostgreSQL (pgcrypto, TimescaleDB)
                                       ├── Redis (token blacklist, cache, rate-limit)
                                       ├── Qdrant (RAG vector store)
                                       ├── Groq LLM (Llama 3.1 8B)
                                       └── Kafka (IoT vitals stream) → TimescaleDB
ML: LSTM (anomaly) · XGBoost (no-show) · MLflow (registry/promotion)
```

---

## Anticipated deep questions + answers

**Why RAG instead of fine-tuning the LLM?**
Medical knowledge changes and must be traceable to sources. RAG grounds answers in retrievable documents and lets me cite + update the corpus without retraining. Fine-tuning would bake in stale knowledge and risk confident wrong dosages. RAG = knowledge; fine-tuning = behavior.

**Why Qdrant (vs FAISS / pgvector)?**
Purpose-built vector DB with production features (filtering, payloads, HNSW ANN, horizontal scaling). FAISS is a library (no persistence/serving layer); pgvector is fine at small scale but I wanted dedicated ANN + metadata filtering.

**Why an LSTM for vitals (vs a Transformer or simple thresholds)?**
Vitals are sequential time-series; thresholds miss patterns. LSTM gates capture long-range temporal dependencies and handle vanishing gradients. A Transformer is heavier/data-hungry; for the sequence lengths and data volume, LSTM was the right cost/accuracy point.

**Why XGBoost for no-show?**
Tabular features (history, lead time, demographics) — gradient-boosted trees dominate tabular, handle missing values, give feature importance, and train fast. I used PR-AUC and class weights because no-shows are the minority class.

**How do you handle the class imbalance?**
PR-AUC over accuracy, `scale_pos_weight` / threshold tuning, and I close the loop: high-risk → SMS reminders, and outcomes feed back as labels for retraining (MLflow promotion gates on AUC/F1).

**How do you evaluate the RAG system?**
Two halves: retrieval (recall@k / hit rate) and generation (faithfulness / answer relevance, RAGAS + spot human review). Splitting them tells me whether a bad answer is a retrieval or a generation problem.

**How do you prevent hallucination in a medical context?**
Grounding in retrieved context, instruct-to-cite + abstain when context is insufficient, low temperature, disclaimers, and never present output as diagnosis. Safety-first prompting.

**How is patient privacy handled? (RGPD)**
Pseudonymization: the public `patients` table holds only a UUID + ML features (no identity). Civil identity lives encrypted (`pgcrypto`, BYTEA) in a separate `secure` schema, joined only by a restricted DPO endpoint. Granular, timestamped consent (IoT/NLP/sharing).

**Walk me through deployment.**
Dockerized FastAPI on Fly.io; managed Postgres (TimescaleDB) + Redis; secrets via Fly secrets; release command bootstraps schema; GitHub Actions CI/CD; pre-push gate runs 508 tests at 80% coverage on real Postgres + Redis.

**Biggest technical challenge?** → see STAR stories below.

**What would you do differently / what are the weaknesses?**
- The Alembic migration chain drifted (a table created after FKs referenced it) — I bootstrapped schema from ORM models as a pragmatic fix and flagged repairing the chain as debt. Lesson: enforce migration tests in CI.
- I'd add proper RAG evaluation harness (RAGAS) in CI, autoscaling, and a feature store for train/serve consistency.
- (Owning weaknesses honestly is a *strength* signal.)

---

## STAR stories (Situation, Task, Action, Result) — have 5 ready

**1. Production debugging cascade (problem-solving + resilience)**
- *S:* First cloud deploy failed repeatedly with different errors.
- *T:* Get the backend live and stable.
- *A:* Worked log-driven, one root cause at a time — monorepo build context, `PYTHONPATH` for the release command, pydantic CORS JSON parsing, asyncpg TLS on the private network, a broken migration chain (switched to ORM `create_all`), missing schema/extensions, then OOM kills.
- *R:* Stable deployment; app runs chat + booking + auth with zero OOM after right-sizing. Learned systematic, hypothesis-driven debugging.

**2. OOM right-sizing (production ML intuition)**
- *S:* App booted then died; later crashed only when the chat endpoint ran.
- *T:* Find why and stabilize.
- *A:* Read logs → kernel OOM kill; ML libraries spiked memory to ~850MB; `uvicorn --reload` doubled it. Removed `--reload`, scaled 512MB→1GB→2GB based on observed RSS.
- *R:* Stable under inference load. Learned that model memory footprint is a first-class production constraint.

**3. Privacy-by-design data modeling (judgment)**
- Pseudonymized schema + encrypted PII + consent → defended a real RGPD constraint in design.

**4. Quality gates (ownership/rigor)**
- Built/maintained 80% coverage gate on real Postgres+Redis; caught a regression before it shipped (a push blocked because the DB wasn't up — the gate did its job).

**5. Shipping a release (delivery)**
- Took the Flutter app to a signed, store-ready Android build (R8, adaptive icons, AAB) + versioning automation.

---

## Numbers & specifics to keep handy (quantify everything)
- 508 tests, ~80% coverage, real PostgreSQL 16 + Redis 7 integration.
- Models: LSTM (anomaly), XGBoost (no-show), RAG (Llama 3.1 8B via Groq), Qdrant.
- Stack: FastAPI (async), SQLAlchemy, Alembic, Docker, Fly.io, GitHub Actions, Flutter.
- ~10 distinct production failures diagnosed & fixed.
- Roles: doctor / secretary / patient / admin (RBAC, JWT).

> If you don't have model accuracy numbers yet — **get them** (run eval, record PR-AUC / recall). "I don't know my model's metrics" is a red flag; quantified results are gold.

---

## Behavioral quick hits
- *Why this field?* (genuine, specific — your PFE journey from notebook to production).
- *Tell me about a failure.* → migration-chain debt: what broke, how you mitigated, the lesson.
- *How do you keep up?* → papers/newsletters/building (name 1–2 you actually follow).
- *Teamwork / conflict / deadline* → prepare one real example each.
