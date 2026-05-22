# Cloud Deployment — Free-Tier Demo

MediSense is built as a 13-service compose stack. The free-tier hosts (Fly.io
hobby, Upstash, Qdrant Cloud, Render) cannot host all of it. This document
describes the **demo subset** we ship to the cloud and the trade-offs we make
versus the local stack.

## Subset shipped to the cloud

| Service | Local | Cloud demo | Why |
|---|---|---|---|
| FastAPI backend | docker-compose | Fly.io app `medisense-backend` | Always on (auto-suspends when idle) |
| Next.js dashboard | docker-compose | Fly.io app `medisense-web` | Same |
| Postgres | TimescaleDB | Fly Postgres (plain) | Free 1 GB, no Timescale extension |
| Redis | docker-compose | Upstash Redis (free) | TLS, eviction-friendly |
| Vector store | Qdrant container | Qdrant Cloud (free 1 GB) | Same client API |
| LLM | Ollama or Groq | **Groq** | No GPU on free hosts |
| IoT simulator | container | Render free worker | Sleeps 15 min idle (acceptable) |

## What we deliberately skip in the cloud

- Kafka + Zookeeper. Setting `KAFKA_BROKERS=""` makes the producer fall back to
  in-process anomaly detection (already supported in `iot.py` and
  `kafka_producer.py`).
- Airflow. Weekly retraining runs locally only; cloud demo serves the existing
  champion model.
- Prometheus + Grafana. Monitoring stays local; for cloud we rely on Fly's
  built-in metrics and the in-app `/admin/system` page.
- MLflow + MinIO. Model registry stays local; cloud demo loads the LSTM
  artefact baked into the backend image.
- TimescaleDB. The 0009 migration is intentionally a no-op when the
  `timescaledb` extension is absent (Fly Postgres is plain PG16) — the rest of
  the schema applies normally.

## One-time setup

```bash
# 1. Install flyctl and authenticate
curl -L https://fly.io/install.sh | sh
fly auth login

# 2. Provision Postgres (free hobby tier)
fly postgres create --name medisense-pg --region cdg --vm-size shared-cpu-1x

# 3. Create the apps and attach Postgres
fly apps create medisense-backend
fly postgres attach medisense-pg --app medisense-backend
fly apps create medisense-web

# 4. Set backend secrets (one-shot — values from your password manager)
fly secrets set --app medisense-backend \
  JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  PGCRYPTO_KEY="$(openssl rand -hex 32)" \
  REDIS_PASSWORD=… REDIS_HOST=… \
  GROQ_API_KEY=gsk_… \
  FCM_SERVICE_ACCOUNT_B64="$(base64 < firebase-key.json)"

# 5. First deploy
fly deploy --config fly.toml
fly deploy --config frontend/web/fly.toml
```

After the GitHub workflow `deploy-fly.yml` is configured with the
`FLY_API_TOKEN` secret, every push to `main` redeploys both apps.

## Verifying the cloud demo

1. `https://medisense-backend.fly.dev/api/v1/health` returns `200`.
2. `https://medisense-web.fly.dev/login` reaches the dashboard.
3. Log in → run a chat → book an appointment → confirm DPA summary loads.
4. Trigger `POST /iot/simulate` and watch `/admin/system` update.

## Risks & known limits

- Cold start: Fly machines suspend after a few minutes idle and take 5–10 s to
  warm up. Warm them before live demos with `fly machine start`.
- 1 GB Postgres: enough for the curated demo dataset only; production loads
  need a paid plan.
- No Timescale: range queries over millions of vitals will be slow on cloud.
- Single replica: the in-process WebSocket fan-out doesn't survive scaling
  beyond one machine — swap to Redis pub/sub before doing so.
