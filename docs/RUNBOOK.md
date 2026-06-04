# MediSense AI — Incident Runbook

Guide de diagnostic et de remédiation pour chaque dépendance externe du système MediSense AI.

---

## Carte des dépendances

```
                        ┌───────────┐
                        │   Nginx   │
                        │ (TLS 1.3) │
                        └─────┬─────┘
                              │
                        ┌─────▼─────┐
                   ┌────│  FastAPI   │────┐
                   │    └─────┬─────┘    │
                   │          │          │
          ┌────────▼──┐  ┌────▼────┐  ┌──▼────────┐
          │ PostgreSQL │  │  Redis  │  │  Qdrant   │
          │    (16)    │  │  (7)    │  │ (vectors) │
          └────────────┘  └────┬────┘  └───────────┘
                               │
                   ┌───────────┼───────────┐
                   │           │           │
              ┌────▼────┐ ┌───▼───┐  ┌────▼────┐
              │  Kafka  │ │  FCM  │  │  Groq   │
              │ (IoT)   │ │(push) │  │  (LLM)  │
              └─────────┘ └───────┘  └─────────┘
```

**Degradation gracieuse** : le système est concu pour continuer a fonctionner en mode degrade lorsque des services non-critiques tombent. Seul PostgreSQL est strictement requis.

---

## 1. PostgreSQL (CRITIQUE)

### Symptomes
- Endpoints renvoient `503 Service Unavailable`
- Health check `GET /health` retourne `"postgres": "unhealthy"`
- Logs : `sqlalchemy.exc.OperationalError: connection refused`

### Diagnostic
```bash
# Verifier que le service tourne
docker compose ps postgres

# Verifier les connexions actives
docker compose exec postgres psql -U medisense_user -d medisense_db -c \
  "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Verifier l'espace disque
docker compose exec postgres df -h /var/lib/postgresql/data
```

### Remediation

| Probleme | Action |
|----------|--------|
| Service arrete | `docker compose up -d postgres` |
| Connexions epuisees (pool full) | Identifier les requetes longues : `SELECT pid, now()-query_start AS duration, query FROM pg_stat_activity WHERE state='active' ORDER BY duration DESC LIMIT 10;` puis `SELECT pg_terminate_backend(pid);` |
| Espace disque plein | Purger les audit_logs anciens (>90j) : `DELETE FROM audit_logs WHERE created_at < now() - interval '90 days';` puis `VACUUM FULL audit_logs;` |
| Replication lag (si replica) | Verifier `pg_stat_replication` sur le primary |

### Impact si indisponible
- **Total** : aucun endpoint ne fonctionne, authentification impossible, aucune lecture/ecriture.

---

## 2. Redis

### Symptomes
- Health check retourne `"redis": "unhealthy"`
- Logs : `aioredis.exceptions.ConnectionError`
- Refresh tokens ne fonctionnent plus (blacklist inaccessible)
- Conversations perdent le contexte (cache RAG vide)

### Diagnostic
```bash
# Verifier le service
docker compose ps redis

# Verifier la memoire
docker compose exec redis redis-cli INFO memory | grep used_memory_human

# Verifier la connectivite
docker compose exec redis redis-cli PING
```

### Remediation

| Probleme | Action |
|----------|--------|
| Service arrete | `docker compose up -d redis` |
| OOM (Out Of Memory) | `redis-cli FLUSHDB` pour vider le cache non-critique, ou augmenter `maxmemory` dans redis.conf |
| Connexion refusee | Verifier le mot de passe dans `.env` (`REDIS_PASSWORD`) correspond a la config Redis |

### Impact si indisponible
- **Auth** : le token blacklist est bypasse — les tokens revoques restent valides jusqu'a expiration JWT (15 min)
- **Chat** : le cache de conversation est perdu — le RAG reconstruit le contexte depuis PostgreSQL (plus lent)
- **Anomalies** : les lectures IoT recentes (buffer Redis) sont perdues — le detecteur utilise uniquement PostgreSQL
- **Degradation** : le systeme continue de fonctionner, avec des performances reduites

---

## 3. Kafka

### Symptomes
- Lectures IoT ne sont plus traitees en temps reel
- Logs : `aiokafka.errors.KafkaConnectionError`
- Consumer lag augmente dans Grafana

### Diagnostic
```bash
# Verifier le service
docker compose ps kafka

# Verifier le consumer lag
docker compose exec kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group medisense-iot-consumer

# Verifier les topics
docker compose exec kafka kafka-topics.sh \
  --bootstrap-server localhost:9092 --list
```

### Remediation

| Probleme | Action |
|----------|--------|
| Broker arrete | `docker compose up -d kafka` — le consumer reprend automatiquement au dernier offset commite |
| Consumer lag eleve | Verifier que le consumer FastAPI tourne (`/health` → `kafka_consumer`). Redemarrer l'app si necessaire |
| Topic manquant | Recreer : `kafka-topics.sh --create --topic iot-readings --partitions 3 --replication-factor 1` |
| Disk full sur broker | Reduire la retention : `kafka-configs.sh --alter --topic iot-readings --add-config retention.ms=86400000` (1 jour) |

### Impact si indisponible
- **IoT** : les lectures biometriques ne sont plus ingerees en temps reel. Le fallback HTTP direct (`POST /iot/readings`) reste fonctionnel
- **Anomalies** : la detection temps-reel est retardee — les anomalies seront detectees au prochain batch ou quand Kafka revient
- **Pas d'impact** sur l'auth, le chat, ou les rendez-vous

---

## 4. Qdrant (Vector Store)

### Symptomes
- Le chat RAG retourne un disclaimer "je ne peux pas acceder a ma base de connaissances"
- Logs : `qdrant_client.http.exceptions.UnexpectedResponse`
- Health check : `"qdrant": "unhealthy"`

### Diagnostic
```bash
# Verifier le service
docker compose ps qdrant

# Verifier la collection
curl -s http://localhost:6333/collections/medisense | jq .

# Verifier l'espace disque
docker compose exec qdrant df -h /qdrant/storage
```

### Remediation

| Probleme | Action |
|----------|--------|
| Service arrete | `docker compose up -d qdrant` |
| Collection corrompue | Restaurer depuis le snapshot : `curl -X POST http://localhost:6333/collections/medisense/snapshots/recover` |
| Espace disque | Supprimer les anciens snapshots : `curl -X DELETE http://localhost:6333/collections/medisense/snapshots/<name>` |

### Impact si indisponible
- **Chat** : le RAG ne peut plus retrouver de documents pertinents. L'assistant repond avec un message d'avertissement et s'appuie uniquement sur le contexte de conversation
- **DPA** : le resume patient perd l'enrichissement RAG (symptomes, historique medical)
- **Pas d'impact** sur l'auth, les rendez-vous, ou l'IoT

---

## 5. Modele LSTM (Anomaly Detection)

### Symptomes
- Les anomalies IoT ne detectent plus les tendances (seulement les seuils statiques)
- Logs : `FileNotFoundError: models/lstm_anomaly_*.pt`
- Logs : `RuntimeError: Error(s) in loading state_dict`

### Diagnostic
```bash
# Verifier que le fichier modele existe
ls -la backend/models/lstm_anomaly_*.pt

# Verifier la version du modele
python -c "import torch; m=torch.load('backend/models/lstm_anomaly_latest.pt', map_location='cpu'); print(m.keys())"
```

### Remediation

| Probleme | Action |
|----------|--------|
| Fichier modele absent | Telecharger depuis MLflow : `mlflow artifacts download -r <run_id> -d backend/models/` |
| Modele incompatible (schema change) | Re-entrainer : `cd backend && python scripts/train_lstm_anomaly.py` |
| GPU OOM a l'inference | Le modele fallback automatiquement sur CPU. Verifier les logs pour confirmer |

### Impact si indisponible
- **Anomalies** : la detection LSTM est desactivee. Le systeme utilise les seuils statiques uniquement (SpO2 < 92%, HR > 120 ou < 50, etc.)
- **Pas de perte de donnees** : les lectures continuent d'etre stockees dans PostgreSQL
- **Pas d'impact** sur les autres fonctionnalites

---

## 6. Modele No-Show (Prediction de rendez-vous manques)

### Symptomes
- `noshow_probability` reste `null` sur les nouveaux rendez-vous
- Logs : `FileNotFoundError: models/noshow_model.pkl`
- Health check : `"noshow_model": "unavailable"`

### Diagnostic
```bash
# Verifier le fichier
ls -la backend/models/noshow_model.pkl

# Verifier les metriques du modele
cat backend/models/noshow_training_report.json | python -m json.tool
```

### Remediation

| Probleme | Action |
|----------|--------|
| Modele absent | Re-entrainer : `cd backend && python scripts/train_noshow_model.py` |
| Metriques sous le seuil (F1 < 0.80, AUC < 0.87) | Verifier la qualite des donnees d'entrainement, augmenter le dataset, ajuster les hyperparametres |

### Impact si indisponible
- **Rendez-vous** : les predictions no-show ne sont pas calculees. Les rappels SMS sont envoyes a tous les patients sans priorisation
- **Pas d'impact** sur les autres fonctionnalites

---

## 7. Groq LLM API

### Symptomes
- Le chat retourne des erreurs ou des reponses vides
- Logs : `httpx.HTTPStatusError: 429 Too Many Requests` ou `503 Service Unavailable`
- DPA summaries ne sont plus generes

### Diagnostic
```bash
# Tester la connectivite
curl -s https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY" | jq .

# Verifier le rate limit restant
# (visible dans les headers de reponse X-RateLimit-Remaining)
```

### Remediation

| Probleme | Action |
|----------|--------|
| Rate limit atteint (429) | Attendre le reset (headers `X-RateLimit-Reset`). Considerer un tier superieur |
| Cle API invalide | Regenerer dans la console Groq et mettre a jour `.env` |
| Service indisponible (503) | Verifier https://status.groq.com — attendre la resolution |

### Impact si indisponible
- **Chat** : l'assistant ne peut plus generer de reponses. Un message d'erreur est affiche au patient
- **DPA** : les resumes automatiques ne sont plus generes. Les actions restent en `PENDING`
- **Pas d'impact** sur l'auth, les rendez-vous, ou l'IoT

---

## 8. Firebase Cloud Messaging (FCM)

### Symptomes
- Les notifications push ne sont plus delivrees
- Logs : `firebase_admin.exceptions.FirebaseError`

### Diagnostic
```bash
# Verifier la config Firebase
python -c "
import base64, json, os
sa = json.loads(base64.b64decode(os.environ['FCM_SERVICE_ACCOUNT_B64']))
print(f'Project: {sa[\"project_id\"]}')
print(f'Client email: {sa[\"client_email\"]}')
"
```

### Remediation

| Probleme | Action |
|----------|--------|
| Service account expire | Regenerer dans la console Firebase > Settings > Service accounts |
| Token device invalide | Les tokens invalides sont automatiquement supprimes de `device_token`. Verifier que le patient a l'app installee |
| Quota FCM depasse | Verifier la console Firebase > Cloud Messaging > Quotas |

### Impact si indisponible
- **Notifications** : les alertes d'anomalies IoT et les rappels ne sont plus envoyes en push
- **Degradation** : le polling inbox (`InboxPoller`) dans l'app mobile prend le relais (intervalle 30s)
- **Pas d'impact** sur les autres fonctionnalites

---

## 9. Salesforce CRM

### Symptomes
- `crm_sync_status` reste `PENDING` ou passe a `FAILED` sur les rendez-vous
- Logs : `httpx.TimeoutException` ou `401 Unauthorized`

### Diagnostic
```bash
# Verifier les rendez-vous en echec de sync
docker compose exec postgres psql -U medisense_user -d medisense_db -c \
  "SELECT count(*), crm_sync_status FROM appointments GROUP BY crm_sync_status;"

# Verifier les erreurs recentes
docker compose exec postgres psql -U medisense_user -d medisense_db -c \
  "SELECT appointment_uuid, crm_last_error, crm_retry_count FROM appointments WHERE crm_sync_status='FAILED' ORDER BY updated_at DESC LIMIT 5;"
```

### Remediation

| Probleme | Action |
|----------|--------|
| Token expire (401) | Regenerer le token OAuth Salesforce dans `.env` |
| Timeout | Verifier la connectivite reseau vers Salesforce. Augmenter le timeout si necessaire |
| Retry epuise | Reset les compteurs : `UPDATE appointments SET crm_sync_status='PENDING', crm_retry_count=0 WHERE crm_sync_status='FAILED';` |

### Impact si indisponible
- **CRM** : les rendez-vous ne sont pas synchronises vers Salesforce. Les donnees restent dans PostgreSQL
- **Pas de perte de donnees** : la sync reprend automatiquement quand le service revient
- **Pas d'impact** sur les autres fonctionnalites

---

## Checklist de diagnostic rapide

```bash
# Tout verifier en une commande
curl -s http://localhost:8000/health | python -m json.tool
```

Le endpoint `/health` retourne l'etat de chaque dependance :

```json
{
  "status": "healthy | degraded | unhealthy",
  "postgres": "ok | unhealthy",
  "redis": "ok | unhealthy",
  "qdrant": "ok | unavailable",
  "kafka_consumer": "running | stopped",
  "noshow_model": "loaded | unavailable",
  "lstm_model": "loaded | unavailable"
}
```

**Regle** : si `status == "degraded"`, le systeme fonctionne mais avec des fonctionnalites reduites. Si `status == "unhealthy"`, PostgreSQL est probablement down — intervenir immediatement.
