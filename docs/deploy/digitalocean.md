# Deploying MediSense AI to DigitalOcean App Platform

This replaces the old Fly.io stack. The whole app is declared in
[`.do/app.yaml`](../../.do/app.yaml) (Infrastructure-as-Code) and deployed with
`doctl`.

## Architecture mapping (Fly → DigitalOcean)

| Old Fly app        | New home on DigitalOcean                          | Why |
|--------------------|---------------------------------------------------|-----|
| `medisense-ai`     | App Platform **service** `backend` (Dockerfile)   | HTTP routing, SSL, autodeploy on push |
| `medisense-web`    | App Platform **service** `web` (Dockerfile)       | Same app, routed at `/` |
| `medisense-pg`     | App Platform **managed dev Postgres** `medisense-pg` | Backups + auto-injected creds |
| `medisense-qdrant` | **Qdrant Cloud** free 1GB cluster                 | App Platform disk is ephemeral — a container Qdrant would lose embeddings every redeploy |
| Redis (Upstash/Fly)| **Upstash** free serverless Redis (`rediss://`)   | Free, TLS, the app already used Upstash |

Backend and web share one app domain. The web app calls `${APP_URL}/api/v1/...`
(same origin), and the backend service is routed at `/api` with the path prefix
preserved — so no CORS round-trips and one SSL cert.

## Prerequisites

```bash
brew install doctl            # DigitalOcean CLI
doctl auth init               # paste a DO API token (with write scope)
```

Authorize DO to read the GitHub repo once, in the dashboard:
**Settings → GitHub → Authorize** (or it prompts on first `apps create`).

## Step 1 — Provision the off-platform data stores

These are not in the spec; create them first and copy their credentials.

### Qdrant Cloud (vector DB)
1. https://cloud.qdrant.io → create a **free 1GB cluster** (Frankfurt).
2. Copy the cluster **host** (`xxxx.eu-central.aws.cloud.qdrant.io`) and an
   **API key**.
3. These become `QDRANT_HOST` and `QDRANT_API_KEY` in the spec.

### Upstash Redis
1. https://upstash.com → create a **free Redis** database (Frankfurt, TLS on).
2. From the database page copy the **endpoint host** and **password**
   (the `rediss://` connection — port `6379`).
3. These become `REDIS_HOST` and `REDIS_PASSWORD`.

After deploy, re-ingest the RAG corpus into the fresh Qdrant cluster:

```bash
cd backend && python scripts/ingest_rag.py   # whatever your ingestion entrypoint is
```

## Step 2 — Generate app secrets

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"   # PGCRYPTO_KEY
```

Collect the rest: `GROQ_API_KEY` (console.groq.com), `JINA_API_KEY`
(jina.ai), and `FCM_SERVICE_ACCOUNT_B64` (base64 of the Firebase service
account JSON, or leave as a dummy for mock FCM).

## Step 3 — Fill in the spec

Edit `.do/app.yaml` and replace every `REPLACE_ME`:
- `REDIS_HOST`, `REDIS_PASSWORD`
- `QDRANT_HOST`, `QDRANT_API_KEY`
- `GROQ_API_KEY`, `JINA_API_KEY`
- `JWT_SECRET_KEY`, `PGCRYPTO_KEY`, `FCM_SERVICE_ACCOUNT_B64`

> Prefer not to commit secrets? Leave them as `REPLACE_ME`, deploy, then set the
> real values in the dashboard under **App → Settings → backend → Environment
> Variables** (they get encrypted at rest). The `init-db` job only needs the
> Postgres binding, which is injected automatically.

## Step 4 — Deploy

```bash
doctl apps create --spec .do/app.yaml
```

This provisions the managed Postgres, runs the `init-db` PRE_DEPLOY job
(`scripts/init_db.py` builds the schema), then starts `backend` and `web`.

Watch it:

```bash
doctl apps list                       # grab the APP_ID
doctl apps logs <APP_ID> backend --follow
```

Subsequent deploys (after editing the spec) — or just push to `main`, since
`deploy_on_push: true`:

```bash
doctl apps update <APP_ID> --spec .do/app.yaml
```

## Step 5 — Verify

```bash
APP_URL=$(doctl apps get <APP_ID> --format DefaultIngress --no-header)
curl -s "$APP_URL/api/v1/health" | jq      # expect 200, db+redis+qdrant healthy
open "$APP_URL"                             # the Next.js dashboard
```

Then update the **mobile** app's production API base URL to `"$APP_URL/api/v1"`
(in `frontend/mobile/.env.production`) and rebuild.

## Notes & gotchas

- **Instance sizes** — `backend` is on `apps-s-1vcpu-2gb` because RAG/ML spikes
  past 850 MB (same reason the Fly VM was 2 GB). Confirm available slugs with
  `doctl apps tier instance-size list`.
- **Postgres SSL** — DO managed Postgres enforces TLS, so the spec sets
  `PGSSLMODE=require` (the Fly stack used `disable` over its private network).
  `asyncpg` honors `PGSSLMODE`.
- **Dev vs managed DB** — `production: false` is the free dev database. For
  automated backups and larger storage, flip it to `true` (a basic managed
  cluster, ~\$7/mo, billed against your \$200 student credit).
- **Cost** — backend (~\$25) + web (~\$5) + dev Postgres (\$0) + Qdrant Cloud
  (\$0) + Upstash (\$0). Drop `backend` to `apps-s-1vcpu-1gb` if RAM allows to
  cut cost.
- **The migration chain is still broken** for a from-scratch `alembic upgrade
  head`; that's why deploy runs `init_db.py` (ORM `create_all`), exactly as Fly
  did via `release_command`.
