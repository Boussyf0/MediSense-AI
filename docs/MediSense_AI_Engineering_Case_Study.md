# MediSense AI — Engineering Case Study

**Role:** AI / ML Engineer & Data Scientist
**Project:** MediSense AI — AI medical assistant & clinic platform for the Moroccan market (PFE @ n.synergy)
**Scope of this document:** End-to-end productionization of a full-stack AI system — from ML services to a live cloud backend and a signed Android release.

---

## 1. Executive Summary

MediSense AI is a production-grade healthcare platform combining a **Retrieval-Augmented Generation (RAG)** medical assistant, **time-series anomaly detection** on IoT vitals, and **no-show prediction** for appointments, exposed through a FastAPI backend and a Flutter mobile app.

This case study documents taking the system from "runs on my laptop" to a **live, stable, internet-reachable deployment** with a **signed, store-ready Android build** — diagnosing and fixing ~10 distinct production failures along the way through log-driven root-cause analysis.

**Outcome:** A fully working stack — mobile app → cloud API → PostgreSQL + Redis — with auth, chat, appointment booking, IoT vitals, and push notifications all functioning end-to-end.

---

## 2. System Architecture

```
┌─────────────────┐     HTTPS      ┌────────────────────────────┐
│  Flutter app    │ ─────────────► │  FastAPI backend (Fly.io)  │
│  (Android/iOS)  │   JWT auth     │  async / uvicorn           │
└─────────────────┘                └────────────┬───────────────┘
                                                 │
              ┌──────────────┬───────────────────┼───────────────┬──────────────┐
              ▼              ▼                    ▼               ▼              ▼
        PostgreSQL 16    Redis 7            Qdrant            Groq LLM       Kafka
        (+ pgcrypto,   (token blacklist,  (vector store /   (llama-3.1-8b   (IoT vitals
        TimescaleDB)    cache, rate-limit) RAG retrieval)    -instant)       stream)
```

### AI / ML components
| Capability | Technique | Stack |
|---|---|---|
| Medical Q&A assistant | **RAG** (semantic retrieval + LLM generation) | Qdrant vector DB, Groq (Llama 3.1 8B), streaming responses |
| Biometric anomaly detection | **LSTM** sequence model on IoT vitals (HR, SpO₂, HRV) | PyTorch, real-time scoring |
| Appointment no-show prediction | **XGBoost** classifier with probability output | scikit-learn / XGBoost |
| MLOps | Model registry, promotion gates (AUC/F1 thresholds) | MLflow |
| Streaming ingestion | IoT vitals pipeline | Kafka consumer → TimescaleDB hypertables |

### Data & privacy engineering
- **Pseudonymized patient model** (RGPD Art. 25): public `patients` table holds only UUID + ML features; civil identity stored **encrypted** (`pgcrypto`, BYTEA) in a separate `secure` schema, joined only by a DPO endpoint.
- **Granular consent** flags (IoT / NLP / data-sharing) with timestamped audit.
- **80% test-coverage gate** enforced in CI against **real PostgreSQL 16 + Redis 7** (not mocks).

---

## 3. Work Delivered

### A. Android release engineering (Flutter)
- Generated an **RSA-2048 upload keystore** (stored outside the repo) and wired release signing via `key.properties` + Gradle (debug-key fallback for local runs).
- Enabled **R8 code shrinking + resource shrinking** with keep-rules for Flutter, Firebase, Health Connect, and speech-to-text.
- Fixed environment selection so **release builds target the production API** (`kReleaseMode` → `.env.production`).
- Generated **adaptive launcher icons** from brand assets; corrected the Android adaptive **safe-zone** (rescaled the brand mark from 42% → 62% of canvas via a PIL crop-and-center script).
- Produced a **signed release APK and AAB** (Play-Store-ready bundle).
- Authored `bump_version.sh` (semantic version + monotonic build number) and `RELEASING.md`.
- Ran a **dependency audit** (`flutter pub outdated`) and applied safe within-constraint upgrades; deferred breaking majors with rationale.

### B. Cloud deployment & DevOps (Fly.io)
- Provisioned and connected managed **PostgreSQL** (TimescaleDB/PG16) and **Redis** (Upstash); created roles, database, and required extensions (`pgcrypto`, `uuid-ossp`) + the `secure` schema.
- Authored an **idempotent one-shot deploy script** and a **schema-bootstrap script** (`init_db.py`) building the schema from SQLAlchemy ORM models.
- Authored an **idempotent demo seeder** (deterministic UUIDs) generating staff/patient accounts, pseudonymized patients, and a spread of appointments with no-show probabilities.
- Fixed the **CI/CD GitHub Actions** deploy workflow for the monorepo build context.
- Managed secrets (JWT, pgcrypto key, DB & Redis passwords) as Fly secrets — never committed.

### C. Production debugging — root-cause cascade
Diagnosed and resolved a chain of deployment failures, each from logs:

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | Build never produced a running host | Monorepo build context: Dockerfile expected `backend/`, `fly.toml` at repo root | Relocated `fly.toml` into `backend/`; corrected deploy working-dir |
| 2 | `ModuleNotFoundError: app` in release cmd | `/app` not on `sys.path` | `PYTHONPATH=/app` + `prepend_sys_path` |
| 3 | Settings fail to load | `CORS_ORIGINS` parsed as JSON by pydantic-settings | Provided value as JSON array |
| 4 | DB `ConnectionResetError` | asyncpg attempting TLS on Fly's already-encrypted private net | `PGSSLMODE=disable` |
| 5 | Migration fails: `patients` missing | **Broken Alembic chain** (table created after FKs reference it) | Switched release cmd to ORM `create_all` (matches test setup) |
| 6 | `schema "secure" does not exist` | `create_all` doesn't create schemas/extensions | Bootstrap script creates schema + extensions first |
| 7 | App boots then dies (port unreachable) | **OOM** at 512 MB loading ML libs + `uvicorn --reload` doubling memory | Removed `--reload`; raised memory |
| 8 | Cold-start 502/503 | scale-to-zero + slow ML import | `min_machines_running = 1` (kept warm) |
| 9 | `/notifications/register-token 500` | `DeviceToken` model missing from package `__init__` → table never created | Registered model in metadata |
| 10 | Runtime OOM on `/chat/stream` | RAG/ML inference spikes to ~850 MB under 1 GB cap | Scaled machine to **2 GB** |

**Result:** stable under real load — repeated chat-stream + booking + auth flows with zero OOM.

### D. Engineering hygiene
- **Clean, scoped Git commits** (`fix(deploy)`, `fix(models)`, `fix(mobile)`, `chore(mobile)`) with descriptive bodies.
- **Pre-push gate** runs the full suite — **508 tests passing at 80% coverage** against live PostgreSQL + Redis.
- Documented residual technical debt (the broken migration chain) with an explicit `TODO` and follow-up plan.

---

## 4. Skills Demonstrated

**AI / ML Engineering**
- RAG system design (vector retrieval + LLM generation, streaming).
- Deploying ML inference (LSTM, XGBoost) inside a production API; reasoning about model memory footprint and right-sizing compute.
- LLM provider integration & graceful degradation (Groq; non-blocking health checks).
- MLOps awareness: model registry, promotion thresholds (AUC/F1).

**Data Science / Data Engineering**
- Time-series modeling on IoT biometric streams; no-show classification with calibrated probabilities.
- Privacy-by-design data modeling: pseudonymization, column-level encryption (`pgcrypto`), consent & audit.
- Streaming ingestion (Kafka → TimescaleDB hypertables).
- Schema-as-code with SQLAlchemy; reproducible seeding with deterministic UUIDs.

**Backend & Cloud / MLOps**
- Async FastAPI, JWT auth, Redis-backed token blacklist & rate limiting.
- Containerization (Docker), Fly.io deployment, managed Postgres/Redis, secrets management.
- CI/CD (GitHub Actions), coverage-gated pre-push hooks.
- **Systematic, log-driven production debugging** — the single most transferable skill shown here.

**Mobile / Delivery**
- Flutter release pipeline: signing, R8 shrinking, adaptive icons, environment management, store artifacts (APK/AAB).

---

## 5. CV-Ready Bullet Points

- Built and deployed **MediSense AI**, a full-stack RAG medical assistant (FastAPI + Flutter) integrating an LLM (Llama 3.1 via Groq), LSTM biometric anomaly detection, and XGBoost no-show prediction.
- Productionized the system on **Fly.io** (managed PostgreSQL/TimescaleDB + Redis), diagnosing and fixing **10+ deployment failures** via log-driven root-cause analysis (build context, async DB/TLS, OOM right-sizing, schema bootstrap).
- Engineered **privacy-by-design** data layer: pseudonymized patients + `pgcrypto`-encrypted PII in an isolated schema, granular consent, RGPD-aligned.
- Established quality gates: **508 integration tests at 80% coverage** on real PostgreSQL + Redis, enforced via pre-push hooks and GitHub Actions CI/CD.
- Shipped a **signed, store-ready Android build** (R8 shrinking, adaptive branding, AAB) with versioning automation.

---

*Generated as a project recap. All figures (test count, coverage, model types, infrastructure) reflect the actual repository and deployment.*
