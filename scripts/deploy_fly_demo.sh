#!/usr/bin/env bash
# One-shot Fly.io demo deploy for the MediSense backend.
#
# PREREQUISITES (you must do these once, they need a browser / external accounts):
#   1. flyctl installed            -> already done (brew install flyctl)
#   2. fly auth login              -> opens browser, log in / sign up (card required)
#   3. A free Groq API key         -> https://console.groq.com/keys
#   4. Fill backend/.deploy/secrets.env  (GROQ_API_KEY at minimum)
#
# Then just run:  ./scripts/deploy_fly_demo.sh
#
# Result: https://medisense-ai.fly.dev  (free TLS, no DNS needed for a demo)
set -euo pipefail

APP="medisense-ai"
PG="medisense-pg"
REGION="cdg"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS="$ROOT/backend/.deploy/secrets.env"

command -v fly >/dev/null || { echo "flyctl not found. Run: brew install flyctl"; exit 1; }
fly auth whoami >/dev/null 2>&1 || { echo "Not logged in. Run: fly auth login"; exit 1; }
[ -f "$SECRETS" ] || { echo "Missing $SECRETS"; exit 1; }
# shellcheck disable=SC1090
set -a; source "$SECRETS"; set +a
if [ -z "${GROQ_API_KEY:-}" ]; then
  echo "⚠ GROQ_API_KEY is empty — backend will boot but AI chat will fail."
  echo "  Get a free key at https://console.groq.com/keys, then:"
  echo "    fly secrets set -a $APP GROQ_API_KEY=gsk_..."
fi

echo "==> 1/5  Ensure app exists"
fly apps list | grep -qw "$APP" || fly apps create "$APP" --org personal

echo "==> 2/5  Ensure Postgres cluster + database/role exist"
if ! fly apps list | grep -qw "$PG"; then
  fly postgres create --name "$PG" --region "$REGION" \
    --vm-size shared-cpu-1x --volume-size 1 --initial-cluster-size 1

  # One-time DB/role bootstrap, only right after creating the cluster.
  # fly.toml expects: db=medisense_db user=medisense_user host=medisense-pg.flycast
  # NOTE: `fly postgres connect` can hang after \q — if it does, press Ctrl-D once.
  fly postgres connect -a "$PG" <<SQL || echo "(db/role may already exist — continuing)"
CREATE ROLE medisense_user LOGIN PASSWORD '${POSTGRES_PASSWORD}';
CREATE DATABASE medisense_db OWNER medisense_user;
\c medisense_db
CREATE EXTENSION IF NOT EXISTS pgcrypto;
GRANT ALL PRIVILEGES ON DATABASE medisense_db TO medisense_user;
\q
SQL
else
  echo "    $PG already exists — skipping creation and DB bootstrap."
fi

echo "==> 3/5  (db/role bootstrap handled above)"

echo "==> 4/5  Set secrets on $APP"
fly secrets set -a "$APP" \
  POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  JWT_SECRET_KEY="$JWT_SECRET_KEY" \
  PGCRYPTO_KEY="$PGCRYPTO_KEY" \
  ${GROQ_API_KEY:+GROQ_API_KEY="$GROQ_API_KEY"} \
  ${REDIS_PASSWORD:+REDIS_PASSWORD="$REDIS_PASSWORD"} \
  ${FCM_SERVICE_ACCOUNT_B64:+FCM_SERVICE_ACCOUNT_B64="$FCM_SERVICE_ACCOUNT_B64"}

echo "==> 5/5  Deploy from backend/ (build context must be backend/; runs 'alembic upgrade head')"
( cd "$ROOT/backend" && fly deploy -a "$APP" )

echo ""
echo "✅ Deployed. Health check:"
echo "   curl https://$APP.fly.dev/api/v1/health"
