# Engineering Skills Practiced — MediSense AI (cloud migration + features)

A field guide to the engineering skills demonstrated while migrating MediSense AI
to production on DigitalOcean and shipping real-time/notification features. Each
section lists **what we actually did**, the **core concepts to master**, the
**gotchas** that cost real debugging time, and an **interview talking point** you
can speak to with confidence because you lived it.

> Stack touched: FastAPI · SQLAlchemy (async) · PostgreSQL · Redis · Qdrant ·
> Docker · DigitalOcean App Platform · Flutter · Firebase Cloud Messaging ·
> RAG (Jina + Groq) · XGBoost/SHAP · BiLSTM · WebSockets · pytest.

---

## 1. Cloud Deployment & Infrastructure-as-Code (DigitalOcean App Platform)

**What we did:** Migrated a 5-piece Fly.io stack to a single DigitalOcean App
Platform app declared entirely in `.do/app.yaml` (two web services — FastAPI
backend + Next.js web — sharing one domain via path routing), deployed and
operated with `doctl`.

**Master these concepts:**
- App spec / IaC: declaring services, routes, env vars, scopes (`RUN_TIME` vs
  `RUN_AND_BUILD_TIME`), and databases in one version-controlled file.
- Path-based ingress: backend at `/api` with `preserve_path_prefix: true`, web
  at `/` — same origin, one TLS cert, no CORS round-trips.
- `doctl apps create` / `update` / `get-deployment` / `logs`; reading deployment
  phases (BUILDING → DEPLOYING → ACTIVE/ERROR).
- Platform-bound variables: `${APP_URL}` is **runtime-only** and does NOT resolve
  at build time — a key trap for `NEXT_PUBLIC_*` values that are inlined at build.

**Gotchas we hit:** `deploy_on_push` rebuilds on *every* commit (even docs);
`${APP_URL}` baked empty into the web bundle (had to hardcode the URL for the
build-time value).

**Interview line:** *"I migrated a multi-service app to DigitalOcean App Platform
as code, using path-based ingress so the API and SPA share one origin, and
debugged build-vs-runtime variable scoping when a runtime binding silently failed
to inline into a Next.js build."*

---

## 2. Containerization & Docker Image Optimization

**What we did:** A from-scratch deploy failed at image-snapshot with *build
resource exhaustion*. Root-caused it to a ~6 GB image: default `torch` pulling
the full CUDA stack (~4 GB of `nvidia-cu*`) plus a training/MLOps kitchen sink
(`transformers`, `mlflow`, `sdv`, `xgboost`, plotting, cloud SDKs). Built a
dedicated `Dockerfile.do` + `requirements-prod.txt`: the **runtime import surface
only** + **CPU-only torch** (`--index-url .../whl/cpu`).

**Master these concepts:**
- Multi-stage builds; what actually lands in the final image layer.
- CPU-only vs CUDA wheels; how transitive deps balloon an image.
- Separating *runtime* deps from *training/dev* deps (you found the true runtime
  surface by grepping module-level imports + checking `joblib.load` needs).
- Build-arg wiring: `ARG NEXT_PUBLIC_API_URL` so the platform can inject a
  build-time value into `next build`.

**Gotchas we hit:** `joblib.load` of a pickled model needs the *creating* library
present (`xgboost`, `shap`) even though nothing imports them directly →
`ModuleNotFoundError` at predict time, not at import.

**Interview line:** *"I cut a 6 GB image that exhausted the build node down to a
slim runtime image by using CPU-only torch and pruning the training stack —
after proving the real runtime dependency surface, including transitive pickle
dependencies."*

---

## 3. Managed Cloud Services (the "off-platform" pattern)

**What we did:** Replaced self-hosted/ephemeral stores with managed services and
wired them over TLS:
- **PostgreSQL → Neon** (the DO dev DB couldn't `CREATE SCHEMA` — only a restricted
  role, no admin to grant; Neon gives an owner role).
- **Redis → Upstash** (`rediss://` TLS).
- **Vector DB → Qdrant Cloud** (HTTPS + API key).
- **Push → Firebase Cloud Messaging** (service account).

**Master these concepts:**
- TLS connection strings (`rediss://`, `sslmode=require`, HTTPS + API key).
- Managed Postgres privilege models (PG 15/16: non-owners lack `CREATE` on the DB
  by default — why `CREATE SCHEMA` failed).
- When a platform's "dev database" is too restricted and an external managed DB
  is the right call.

**Interview line:** *"I diagnosed a Postgres privilege wall — the platform dev DB
gave a non-owner role that couldn't create the schema our RGPD encryption needed —
and moved to an external managed Postgres with owner rights, validating it by
running the real bootstrap script against it before deploying."*

---

## 4. Backend Engineering (FastAPI + async SQLAlchemy)

**What we did:** Added endpoints and a notification subsystem: a `confirm`
appointment transition, a durable `Notification` model, and `GET /notifications` +
mark-read, all with role-based access control.

**Master these concepts:**
- FastAPI: routers, `Depends` for auth/RBAC, Pydantic request/response models,
  status codes, HTTPBearer (absent header → **403**, not 401).
- Async SQLAlchemy: `select()`, `flush()` (let middleware commit), FK ordering on
  insert, ORM `create_all` vs Alembic migrations.
- Response-vs-storage type mismatches: a payload stored as `list[dict]` but a
  schema typed `list[str]` → pydantic `ValidationError` → 500.

**Gotchas we hit:** `asyncio.gather` returns results positionally — unpacking a
function that returns a *tuple* without destructuring left a `(list, bool)` tuple
masquerading as the data and crashed a `" ".join(...)`.

**Interview line:** *"I shipped RBAC'd FastAPI endpoints with a durable
notifications model, and fixed two production 500s from type mismatches — a
`list[dict]` payload serialized against a `list[str]` schema, and a tuple left
un-destructured after `asyncio.gather`."*

---

## 5. Testing, Coverage & TDD Discipline

**What we did:** Held a strict coverage gate (80%, real ~94%) across every change;
wrote happy-path + RBAC + error-path tests for each new endpoint; added regression
tests that reproduce the exact bug before fixing.

**Master these concepts:**
- pytest with real Postgres + Redis fixtures, rolled back per test.
- The endpoint testing contract: 200/201, auth rejection (403), primary error
  (404/409/422).
- **Coverage tracer internals:** the default C tracer drops `await` line events on
  Python 3.12+, under-reporting async code (~80% reported vs ~94% real). Fix:
  `core = sysmon` in `.coveragerc` (PEP 669 `sys.monitoring`).
- Why mocked tests miss bugs: the DPA build was fully mocked, so the real
  `list[dict]` serialization path never ran in tests — added a test with the real
  shape.

**Interview line:** *"I found our coverage gate was measuring fiction — the
default tracer drops async line events on 3.12 — and switched to the
`sys.monitoring` core, which revealed the suite was actually at 94%, not 80%."*

---

## 6. Production Debugging & Observability

**What we did:** Drove every fix from live evidence — `doctl apps logs`,
`get-deployment` error codes (`BuildJobTerminated`, `DeployContainerExitZero`,
`DeployContainerExitNonZero`), and reproducing 500s with targeted curl/WS calls.

**Master these concepts:**
- `run_command` is **shlex-split, not shell-run** on App Platform → `&&` was passed
  as argv and uvicorn never started (exit 0). Fix: a real `start.sh`.
- Distinguishing exit-zero-early (process ended) from exit-nonzero (crash) from
  health-check failures.
- Reading a Python traceback in container logs back to the exact line.

**Interview line:** *"I learned the platform runs `run_command` via shlex, not a
shell, so my `init && uvicorn` chain silently exited 0 — I moved startup into a
script and made the container a proper long-running process."*

---

## 7. ML/AI Systems in Production

**What we did:** Operated a full RAG pipeline (Qdrant retrieval → Jina rerank →
Groq generation) end-to-end in the cloud; served a no-show model
(**XGBoost + SHAP** via joblib) and a **BiLSTM** anomaly detector; ingested a
curated medical corpus (~3,200 vectors, 1024-dim Jina v3 + BM25 sparse).

**Master these concepts:**
- RAG: dense + sparse hybrid retrieval, reranking, grounded generation, sources.
- Hosted embeddings/inference to keep heavy models off the API box.
- Model serving: lazy loading, graceful degradation (mock/None when a model file
  is absent), and explainability (SHAP contributions in the response).
- Rule-based safety nets alongside ML (SpO₂<90 / HR≥130 critical alerts) so the
  feature works during cold-start or a missing model.

**Interview line:** *"I ran a hybrid RAG pipeline in production and served an
XGBoost+SHAP risk model — and I always pair the ML path with a deterministic
rule-based fallback so the feature degrades gracefully."*

---

## 8. Real-time & Offline-safe Notifications

**What we did:** Built appointment-lifecycle notifications that work **even when
the recipient is offline**, with two layers:
- **Durable DB rows** (`Notification`) written at event time → an offline/logged-out
  *account* sees it on next login (the source of truth).
- **FCM push** (store-and-forward) → an offline *app* gets it on reconnect.
Plus real-time WebSocket alerts for IoT anomalies (single-process pub/sub,
broadcast to a role group), verified with a live WS round-trip.

**Master these concepts:**
- The difference between "app offline" (FCM queues) and "account offline" (needs
  durable storage) — and why you need both.
- WebSocket auth via query-param token (browsers can't set WS headers).
- Best-effort side effects: push failures must never break the triggering request.

**Interview line:** *"For offline-safe notifications I separated the two failure
modes: a durable DB row makes a logged-out account see the event on next login,
while FCM store-and-forward covers a backgrounded app — the DB row is the source
of truth, push is best-effort."*

---

## 9. Mobile Release Engineering (Flutter)

**What we did:** Built signed release APKs (`flutter build apk --release`),
verified the **v2 signature** against the upload keystore with `apksigner`,
confirmed the baked `API_BASE_URL` and Firebase project inside the artifact, and
wired the inbox poller to the new notifications endpoint.

**Master these concepts:**
- Release signing (keystore + `key.properties`), `apksigner verify --print-certs`,
  cert SHA-256 matching.
- Build-time env baking (`flutter_dotenv` `.env.production`, `kReleaseMode`).
- Verifying an artifact end-to-end (unzip the APK, grep the baked URL).
- FCM client lifecycle: `getToken()` → `register-token` on login, `unregister` on
  logout; same Firebase project as the backend service account.

**Interview line:** *"I shipped signed release APKs and verified them end-to-end —
matched the signing cert SHA-256 to the upload key and confirmed the baked backend
URL and Firebase project inside the artifact."*

---

## 10. Security, Secrets & Compliance

**What we did:** Kept every credential out of git — real values only in a
gitignored local spec (`.do/app.local.yaml`) and gitignored key files
(`secrets-firebase-adminsdk.json`), with `type: SECRET` placeholders in the
committed template. Preserved an RGPD `secure` schema (pgcrypto-encrypted patient
identity) end-to-end through the migration.

**Master these concepts:**
- Secret hygiene: committed template with `REPLACE_ME` + `type: SECRET`, real
  values injected at deploy; `git check-ignore` before any add.
- Platform secrets (DO encrypted env vars) vs build-time vs runtime exposure.
- RGPD-by-design: separate encrypted schema for civil identity, two-step erasure.
- Knowing that anything pasted/printed should be rotated afterward.

**Interview line:** *"I treated secrets as build-time vs runtime concerns, kept a
committed IaC template with `SECRET` placeholders and real values only in a
gitignored spec, and preserved an RGPD-compliant encrypted identity schema across
the DB migration."*

---

## 11. Git & Release Workflow

**What we did:** Feature-branch development, a pre-push hook enforcing the coverage
gate, conventional commits (no AI attribution), force-adding a needed binary past
a broad ignore (`git add -f` for the 2.2 MB model), and merging to a stable `main`.

**Master these concepts:**
- Pre-push gates (tests + coverage before every push).
- Conventional commit messages with a clear *why*.
- `git check-ignore`, `git add -f`, and keeping secrets/large artifacts handled
  deliberately.

---

## TL;DR — the headline skills for your profile

| Area | Skill |
|------|-------|
| Cloud/DevOps | DigitalOcean App Platform, IaC app spec, `doctl`, path-based ingress |
| Containers | Docker multi-stage, image slimming, CPU-only ML wheels, build-arg injection |
| Managed services | Neon, Upstash, Qdrant Cloud, Firebase — TLS + privilege models |
| Backend | FastAPI, async SQLAlchemy, RBAC, Pydantic, durable event modeling |
| Testing | pytest, coverage internals (sysmon), endpoint testing contract, regression-first |
| Debugging | Log-driven RCA, deploy error codes, shlex vs shell, traceback reading |
| ML in prod | RAG (hybrid + rerank), XGBoost+SHAP, BiLSTM, graceful degradation |
| Real-time | WebSockets, FCM, offline-safe two-layer notification design |
| Mobile | Flutter release signing, artifact verification, FCM client lifecycle |
| Security | Secret hygiene, IaC secrets, RGPD encrypted schema |
