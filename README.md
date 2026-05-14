# MediSense AI — Cognitive HealthTech Platform

![CI](https://github.com/Boussyf0/MediSense-AI/actions/workflows/ci.yml/badge.svg?branch=main)
![Coverage](https://img.shields.io/badge/coverage-80%25-brightgreen)
![Tests](https://img.shields.io/badge/tests-333%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

**Candidate:** Abderrahim Boussyf
**Institution:** EMSI Marrakech — Data Science & IA
**Company:** n.synergy
**Duration:** 5 months — 10 Sprints — 2025/2026

---

## What is MediSense AI?

MediSense AI transforms a medical clinic into a proactive, augmented information system. In 24 hours, the platform:

1. Detects a biometric anomaly during a patient's sleep (IoT + LSTM)
2. Sends a non-alarming push notification at wake-up time
3. Runs a cognitive triage via natural language chatbot (RAG + LLM provider toggle: Ollama/Groq)
4. Predicts no-show probability and books the appointment (XGBoost)
5. Syncs the CRM automatically (Salesforce Apex webhook)
6. Prepares a 3-column AI summary for the doctor — saving 11 minutes per consultation

---

## Architecture — 3 AI Pipelines

```
Pipeline 1 — IoT / Deep Learning
  Samsung Watch → MQTT/BLE → Kafka → TimescaleDB → LSTM → anomaly_detected

Pipeline 2 — RAG / LLM
  Patient chat → NLP → Qdrant (84k medical chunks) → cross-encoder → Ollama or Groq → response

Pipeline 3 — Predictive ML
  Patient profile → XGBoost (8 features + SHAP) → no-show probability → smart agenda
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI (async) + Uvicorn |
| Database | PostgreSQL 16 + pgcrypto (AES-256) |
| Cache / Sessions | Redis 7 |
| Vector DB | Qdrant |
| LLM Inference | Ollama (local) or Groq API (demo mode) |
| Reverse Proxy | Nginx (TLS 1.3) |
| ML | XGBoost, LightGBM, Scikit-learn |
| Deep Learning | PyTorch / TensorFlow (LSTM) |
| IoT Streaming | Apache Kafka + TimescaleDB |
| MLOps | MLflow + Evidently AI + Airflow |
| Auth | JWT (python-jose) + bcrypt + Redis blacklist |
| Migrations | Alembic |
| Testing | pytest + pytest-asyncio + pytest-cov |
| Containers | Docker + Docker Compose |
| CI/CD | GitHub Actions |

---

## Project Structure

```
MediSense-AI/
├── backend/                        # FastAPI application
│   ├── app/
│   │   ├── main.py                 # App entry point, middleware, lifespan
│   │   ├── core/
│   │   │   ├── config.py           # Settings from .env (pydantic-settings)
│   │   │   ├── security.py         # JWT creation/validation, bcrypt, Redis blacklist
│   │   │   └── dependencies.py     # FastAPI auth dependencies + RBAC
│   │   ├── api/v1/
│   │   │   ├── router.py           # Aggregates all endpoint routers
│   │   │   └── endpoints/
│   │   │       ├── health.py       # GET /health — checks postgres + redis
│   │   │       └── auth.py         # POST /login, /refresh, /logout — GET /me
│   │   ├── db/
│   │   │   ├── session.py          # Async SQLAlchemy engine + get_db dependency
│   │   │   └── models/
│   │   │       ├── user.py         # Staff users (doctor, secretary, admin)
│   │   │       └── patient.py      # Pseudonymized patients + encrypted identity
│   │   └── schemas/
│   │       └── auth.py             # Pydantic request/response validation schemas
│   ├── alembic/                    # Database migrations
│   │   ├── env.py                  # Async Alembic environment
│   │   └── versions/
│   │       └── 20260401_000000_baseline_sprint1.py
│   ├── tests/
│   │   ├── conftest.py             # pytest fixtures (test DB, async client)
│   │   ├── test_health.py          # US-01: health endpoint tests
│   │   └── test_auth.py            # US-03/04: JWT + RBAC tests
│   ├── requirements.txt
│   └── Dockerfile                  # Single-stage build (arm64-friendly)
├── .github/
│   └── workflows/
│       └── ci.yml                  # CI: compile + tests + Docker build smoke check
├── nginx/
│   └── nginx.conf                  # TLS 1.3, rate limiting, HTTP→HTTPS redirect
├── scripts/
│   ├── init_db.sql                 # PostgreSQL init: pgcrypto, schema, tables
│   └── generate_certs.sh           # Self-signed TLS cert for local dev
├── docker-compose.yml              # 6 services: postgres, redis, fastapi, qdrant, ollama, nginx
├── .env.example                    # Environment variables template (never commit .env)
└── .gitignore
```

---

## Sprint Progress

### Sprint 1 — Foundation Architecture COMPLETE
**Branch:** `sprint/1-foundation-architecture`
**Goal:** All services running, secured, and authenticated

| User Story | Description | Status |
|-----------|-------------|--------|
| US-01 | docker-compose launches all services in 1 command. `/health` responds 200 in < 2s | Done |
| US-02 | HTTPS on all endpoints. TLS 1.3 via nginx. OWASP headers | Done |
| US-03 | OAuth2/JWT: access token (15min) + refresh (7d) + Redis revocation on logout | Done |
| US-04 | RBAC: 4 roles (patient, doctor, secretary, admin). Unauthorized returns 403 | Done |
| US-05 | RGPD DB schema: pseudonymized patients UUID + AES-256 encrypted identity | Done |
| US-45 | Swagger auto-docs at `/api/v1/docs` | Done |

**What was built:**

**Infrastructure:**
- 6-service Docker Compose stack (postgres, redis, fastapi, qdrant, ollama, nginx)
- PostgreSQL 16 with pgcrypto extension for AES-256 at-rest encryption
- Redis 7 with AOF persistence and password auth
- Nginx TLS 1.3 reverse proxy with HTTP→HTTPS redirect and rate limiting
- Ollama + Qdrant provisioned (used from Sprint 3)

**Backend:**
- FastAPI async application with lifespan startup verification
- JWT authentication: access/refresh token pair + Redis blacklist for revocation
- RBAC via FastAPI dependency injection: `require_doctor`, `require_admin`, etc.
- Security headers middleware on every response (HSTS, X-Frame-Options, CSP)
- Global exception handler (no stack traces in production)

**Database:**
- `public.users` — staff accounts with bcrypt hashed passwords
- `public.patients` — UUID-only pseudonymized records (no civil identity)
- `secure.patients_identity` — AES-256 encrypted name/phone/email (separate schema)
- `public.audit_logs` — immutable append-only access log (RGPD Art.30)
- `public.consent_logs` — immutable consent history (RGPD Art.7)
- `public.appointments` — scheduling table (ORM model in Sprint 2)
- Alembic baseline migration tracking

**Bugs fixed during Sprint 1:**
- `email-validator` missing from requirements.txt (`--no-deps` Dockerfile issue)
- `limit_req_zone` placed inside `server{}` block instead of `http{}` (nginx scope error)
- TLS 1.3 cipher syntax incompatible with `ssl_ciphers` directive
- SQLAlchemy enum `native_enum=False` + `values_callable` required for VARCHAR storage
- Pydantic `UserResponse.user_uuid: str` rejected UUID object — changed to `UUID` type

---

### Sprint 2 — RGPD & Consent (upcoming)
**Branch:** `sprint/2-rgpd-consent`

User Stories: US-06 (granular consent), US-07 (RGPD data export), US-08 (right to erasure), US-46 (audit logs endpoint)

---

### Sprint 3 — RAG Pipeline & LLM Agents (upcoming)
**Branch:** `sprint/3-rag-pipeline`

User Stories: US-09 (LLM provider toggle Ollama/Groq), US-10 (84k chunks in Qdrant), US-11 (symptom chatbot FR/AR/Darija), US-12 (cross-encoder re-ranking)

---

### Sprint 4 — Agents & DPA (upcoming)
**Branch:** `sprint/4-agents-dpa`

User Stories: US-13 (IoT context in chat), US-14 (orchestrator agent), US-15 (Redis conversation memory), US-41 (DPA 3-column view), US-42 (Human-in-the-Loop)

---

### Sprint 5 — No-Show ML Model (upcoming)
**Branch:** `sprint/5-noshow-ml`

User Stories: US-17 (feature engineering), US-18 (XGBoost vs LightGBM vs CatBoost), US-19 (color-coded agenda), US-20 (predict endpoint < 200ms), US-22 (SMOTE class balancing), US-SMS (smart reminders: no-show > 30%, max 2, opt-out respected)

---

### Sprint 6 — Salesforce & MLOps (upcoming)
**Branch:** `sprint/6-salesforce-mlops`

User Stories: US-24 (Salesforce webhook), US-33 (MLflow model registry), US-37 (GitHub Actions CI/CD), US-38 (OWASP ZAP scan), US-43 (secretary Salesforce tasks)

---

### Sprint 7 — IoT Pipeline & LSTM (upcoming)
**Branch:** `sprint/7-iot-lstm`

User Stories: US-25 (Kafka ingestion 10 msg/s), US-26 (TimescaleDB hypertable), US-27 (bidirectional LSTM AUC-ROC > 0.85), US-28 (anomaly detection 2 windows), US-29 (morning push notification)

---

### Sprint 8 — Integration & Production (upcoming)
**Branch:** `sprint/8-integration-production`

User Stories: US-30 (Kafka degraded mode), US-34 (Airflow weekly retraining), US-35 (Evidently AI drift detection), US-36 (auto-rollback F1 < 10%)

---

### Sprint 9 — Flutter Mobile Patient App (upcoming)
**Branch:** `sprint/9-flutter-mobile`

User Stories: US-47 (onboarding + auth + consent), US-48 (chatbot Darija/FR/AR + voice), US-49 (IoT dashboard), US-50 (booking + Salesforce sync), US-55/56/59 (results + reminders + medication alerts)

---

### Sprint 10 — Doctor Dashboard & Monitoring (upcoming)
**Branch:** `sprint/10-nextjs-dashboard`

User Stories: US-51/52/53 (doctor dashboard + DPA + smart agenda), US-54 (WebSocket alerts + Twilio), US-57 (Grafana dashboards), US-60 (admin UI)

---

## Quick Start

### Prerequisites
- Docker Desktop running
- openssl installed

### 1. Clone and configure
```bash
git clone https://github.com/Boussyf0/MediSense-AI.git
cd MediSense-AI
cp .env.example .env
```

Edit `.env` — generate real secrets:
```bash
openssl rand -hex 32   # for JWT_SECRET_KEY
openssl rand -hex 32   # for PGCRYPTO_KEY
openssl rand -hex 16   # for REDIS_PASSWORD
openssl rand -hex 16   # for POSTGRES_PASSWORD
```

### 2. Generate TLS certificate (local dev only)
```bash
bash scripts/generate_certs.sh
```

### 3. Launch all services
```bash
docker compose up -d
docker compose ps      # all should be healthy within 30s
```

### 4. Verify everything works
```bash
# Health check
curl -k https://localhost/api/v1/health

# Login
curl -k -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medisense.ai","password":"Admin1234!"}'

# Swagger UI
open https://localhost/api/v1/docs
```

### 5. Configure LLM provider

#### Option A — Ollama local (default, RGPD-friendly)
```bash
docker exec medisense_ollama ollama pull mistral:7b-instruct

# .env
LLM_PROVIDER=ollama
OLLAMA_HOST=ollama
OLLAMA_MODEL=mistral:7b-instruct
```

#### Option B — Groq API (fast jury demo)
```bash
# .env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...      # from https://console.groq.com
GROQ_MODEL=llama-3.1-8b-instant
```

> Note: `LLM_PROVIDER=groq` sends prompts to a third-party cloud API (not on-prem RGPD mode).

---

## Evaluation evidence runbook

```bash
# Retrieval metrics + latencies (writes JSON artifact)
docker exec medisense_fastapi bash -lc "cd /app && python scripts/run_evaluation.py --output results/evaluation_83k.json"

# LLM provider benchmark (first-token/total/retrieval p50/p95)
docker exec medisense_fastapi bash -lc "cd /app && python scripts/benchmark_llm_provider.py --output results/llm_provider_benchmark.json"

# Red-team safety campaign (writes JSON artifact)
docker exec medisense_fastapi bash -lc "cd /app && python scripts/run_red_team_eval.py --output results/red_team_eval_final.json"
```

Main artifacts:
- `backend/results/evaluation_83k.json`
- `backend/results/llm_provider_benchmark.json`
- `backend/results/red_team_eval_final.json`

CI also uploads `red-team-ci-report` artifact from `.github/workflows/ci.yml` (deterministic safety smoke).

---

## Database Migrations (Alembic)

```bash
# Generate migration after changing a model
docker exec medisense_fastapi bash -c \
  "cd /app && PYTHONPATH=/app alembic revision --autogenerate -m 'your_description'"

# Apply all pending migrations
docker exec medisense_fastapi bash -c \
  "cd /app && PYTHONPATH=/app alembic upgrade head"

# Check current state
docker exec medisense_fastapi bash -c \
  "cd /app && PYTHONPATH=/app alembic current"

# Rollback one step
docker exec medisense_fastapi bash -c \
  "cd /app && PYTHONPATH=/app alembic downgrade -1"
```

---

## RGPD Compliance (Article 25 — Privacy by Design)

| Requirement | Implementation |
|-------------|---------------|
| Pseudonymization | Patient UUID only in all tables — civil identity in separate encrypted schema |
| Encryption at rest | AES-256 via pgcrypto on `secure.patients_identity` |
| Encryption in transit | TLS 1.3 mandatory — enforced at nginx level |
| Granular consent | 3 separate opt-ins: IoT / NLP / doctor sharing |
| Right of access | `GET /patient/data/export` returns full JSON (Sprint 2) |
| Right to erasure | `DELETE /patient/{uuid}` cascades to DB + Qdrant vectors (Sprint 2) |
| Audit trail | Immutable `audit_logs` — every data access recorded |
| Data minimization | Raw biometrics retained 30 days max, then aggregated features only |

---

## Security Architecture

| Layer | Mechanism |
|-------|-----------|
| Transport | TLS 1.3 only (nginx), HSTS 1 year |
| Authentication | JWT HS256, 15-min access + 7-day refresh |
| Token revocation | Redis blacklist with auto-expiry TTL |
| Passwords | bcrypt rounds=12 (~300ms — brute force resistant) |
| Authorization | RBAC via FastAPI dependency injection |
| Rate limiting | 5 req/min on `/auth/login`, 60 req/min on `/api/` (nginx) |
| Headers | X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy |
| DB encryption | AES-256 pgcrypto for sensitive fields, TLS for connections |
| Secrets | Environment variables only, never in code or git |

---

## Target KPIs (End of Sprint 8)

| Metric | Target | Sprint |
|--------|--------|--------|
| F1-Score No-Show model | > 0.80 | 5 |
| AUC-ROC LSTM anomaly detection | > 0.85 | 7 |
| RAG response latency P95 | < 150ms | 3 |
| REST API response P95 | < 200ms | 1 Done |
| No-Show rate reduction | > 20% | 8 |
| System uptime | > 99.5% | 6 |
| RAGAS Faithfulness | > 0.85 | 3 |

---

## License

Confidential — PFE 2025/2026 — EMSI Marrakech / n.synergy
