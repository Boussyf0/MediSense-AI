# Sprint 8 — Intégration & Production : Détail Complet
**06 Juillet – 19 Juillet 2026 | Statut : ⏳ À VENIR**

> Ce document explique **ce qui est déjà durci en production** (Sprints 1-6), **ce qui est conçu pour Sprint 8**, et **ce sur quoi tu dois te concentrer** en tant que profil Data Science & IA pour comprendre la résilience du pipeline MLOps, le réentraînement automatisé et la détection de dérive des données.

---

## Table des Matières

1. [Vue d'ensemble du Sprint 8](#1-vue-densemble-du-sprint-8)
2. [Production hardening déjà livré (Sprints 1-6)](#2-production-hardening-déjà-livré-sprints-1-6)
3. [US-30 — Mode dégradé Kafka](#3-us-30--mode-dégradé-kafka)
4. [US-34 — DAG Airflow réentraînement hebdomadaire](#4-us-34--dag-airflow-réentraînement-hebdomadaire)
5. [US-35 — Evidently AI : détection de dérive des données](#5-us-35--evidently-ai--détection-de-dérive-des-données)
6. [US-36 — Auto-rollback modèle si F1 chute > 10%](#6-us-36--auto-rollback-modèle-si-f1-chute--10)
7. [Infrastructure technique & artefacts prévus](#7-infrastructure-technique--artefacts-prévus)
8. [Métriques cibles & validation](#8-métriques-cibles--validation)
9. [Décisions d'architecture & leçons de conception](#9-décisions-darchitecture--leçons-de-conception)
10. [Ce sur quoi te concentrer — Profil DS/IA](#10-ce-sur-quoi-te-concentrer--profil-dsia)

---

## 1. Vue d'ensemble du Sprint 8

### Objectif
Compléter le cycle de vie MLOps en production :
- garantir la résilience du pipeline IoT face à une panne Kafka (US-30),
- automatiser le réentraînement hebdomadaire du modèle No-Show via Airflow (US-34),
- détecter la dérive des données en production avec Evidently AI (US-35),
- restaurer automatiquement la version précédente du modèle si la performance chute (US-36).

### Résultat cible

| Axe évalué | Score cible | Lecture |
|------------|:-----------:|---------|
| Résilience IoT | **4.0 / 5** | Aucune perte de données biométriques même si Kafka est indisponible 1h. |
| Maturité MLOps | **4.5 / 5** | Boucle complète : production → drift détecté → réentraînement → promotion/rollback automatique. |
| Observabilité | **4.0 / 5** | Rapports Evidently accessibles ; alertes email/Slack sur drift PSI > 0.25. |
| Automatisation | **4.0 / 5** | DAG Airflow exécuté sans intervention humaine chaque lundi 02h00 UTC. |

### User Stories couvertes

| US | Description | Story Points | Priorité | Statut |
|----|-------------|:------------:|:--------:|:------:|
| US-30 | Mode dégradé Kafka : buffer local + reprise automatique à reconnexion | 8 | Could | ⏳ |
| US-34 | DAG Airflow : réentraînement hebdomadaire automatique | 8 | Could | ⏳ |
| US-35 | Evidently AI : détection dérive données (PSI + feature importance shift) | 5 | Could | ⏳ |
| US-36 | Auto-rollback : si F1 chute > 10% en prod → restauration version N-1 | 5 | Could | ⏳ |
| **Total** | | **26 pts** | | |

### Ce qui doit être livré

```text
backend/
├── dags/
│   └── retrain_noshow_weekly.py         # US-34 DAG Airflow PythonOperator
├── app/
│   ├── services/
│   │   └── kafka_consumer.py            # US-30 mode dégradé (dépend Sprint 7)
│   └── api/v1/endpoints/
│       └── drift.py                     # US-35 GET /admin/drift-report
├── scripts/
│   ├── detect_drift.py                  # US-35 Evidently rapport PSI
│   └── auto_rollback.py                 # US-36 MLflow alias rollback
docs/
└── SPRINT_8_DETAILS.md                  # ce fichier
docker-compose.yml                       # +airflow service
requirements.txt                         # +apache-airflow +evidently
```

---

## 2. Production hardening déjà livré (Sprints 1-6)

Avant d'implémenter Sprint 8, un socle de production solide a été posé au fil des sprints précédents. Ces éléments sont **déjà en production** et couvrent la majorité des exigences de robustesse.

### Sécurité réseau et transport

**Fichier :** `nginx/nginx.conf`

| Mécanisme | Configuration | Statut |
|-----------|---------------|:------:|
| TLS 1.3 uniquement | `ssl_protocols TLSv1.3` | ✅ |
| HSTS | `Strict-Transport-Security: max-age=31536000; includeSubDomains` | ✅ |
| Rate limiting auth | 5 req/min (burst=3) — zone `auth_limit` | ✅ |
| Rate limiting API | 60 req/min (burst=20) — zone `api_limit` | ✅ |

### Headers de sécurité applicatifs

**Fichier :** `app/main.py` (lignes 109-139), middleware `add_security_headers`

```python
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; script-src 'self'; ...
```

La CSP est assouplie uniquement pour `/docs*` et `/static*` (Swagger UI nécessite `unsafe-inline`). Tous les endpoints API appliquent la politique stricte.

### Health check & observabilité

**Fichier :** `app/api/v1/endpoints/health.py`

```
GET /api/v1/health → 200
{
  "status": "healthy" | "degraded",
  "version": "1.0.0-sprint1",
  "services": {
    "postgres": "ok" | "error: <msg>",
    "redis": "ok" | "error: <msg>"
  }
}
```

Utilisé par Docker Compose `healthcheck` et les sondes Kubernetes. Si PostgreSQL ou Redis est indisponible, retourne `degraded` (pas 503 — évite les restart loops inutiles pour les sondes liveness).

### Authentification & révocation JWT

**Fichier :** `app/api/v1/endpoints/auth.py`

- JWT HS256, expiration configurable (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Blacklist Redis** : à la déconnexion, le JTI est inscrit avec TTL = durée restante du token
- Tous les endpoints vérifient la blacklist avant de traiter la requête

### Circuit breaker Salesforce

**Fichier :** `app/services/salesforce_client.py` (Sprint 6 — US-24)

- État en mémoire processus (Redis distribué = US-30+ extension Sprint 8)
- **Limite** : incompatible avec `uvicorn --workers N` (plusieurs processus = états désynchronisés)
- **Fix Sprint 8** : migrer l'état du circuit breaker vers Redis (`cb:salesforce:state` key)

### Pipeline CI/CD

**Fichier :** `.github/workflows/ci.yml`

| Gate | Seuil | Comportement si raté |
|------|:-----:|----------------------|
| Couverture tests | ≥ 80% | `pytest --cov-fail-under=80` → exit 1 |
| Red-team sécurité | `strict_pass_rate = 1.0` | Vérifie `red_team_eval_ci.json` → exit 1 |
| ML quality gate | F1 ≥ 0.80 **et** AUC ≥ 0.87 | Vérifie `noshow_training_report.json` → exit 1 |
| Build Docker + push GHCR | main/release uniquement | `ghcr.io/${{ github.repository_owner }}/medisense-backend` |

**Optimisations CI :**
- Cache pip : `hashFiles('backend/requirements.txt')` → ~60% de gain sur les runs répétés
- `python -m compileall` avant les tests → détecte les erreurs de syntaxe sans lancer pytest
- `docker system prune -af` avant le build → évite les `no space left on device` sur les runners GitHub

### OWASP ZAP

**Fichier :** `.github/workflows/security-zap.yml`

- Scan baseline hebdomadaire (lundi 03h00 UTC)
- Résultat : **0 vulnérabilité High** — exceptions documentées dans `.zap/rules.tsv`
- Artefact : rapport HTML uploadé après chaque scan

### Audit logs RGPD

**Fichier :** `app/core/audit.py`

Conforme Article 30 RGPD — chaque accès/modification de données patient est tracé avec `actor_id`, `action`, `resource`, `ts`, `ip`.

---

## 3. US-30 — Mode dégradé Kafka

### Problème
Si le broker Kafka est indisponible (maintenance, crash réseau), les données biométriques de Sprint 7 seraient perdues — l'app Flutter recevrait une erreur 503 et l'utilisateur cesserait de recevoir ses alertes santé.

### Solution : Buffer CSV local + reprise automatique

```
Kafka indisponible (NoBrokersAvailable)
    ↓
kafka_consumer.py → bascule vers local buffer
    ↓
Fichier CSV : /tmp/kafka-buffer/{patient_id}_{ts}.csv
    ↓
Background task asyncio (30s interval)
    ↓
Scrute /tmp/kafka-buffer/ → tente reconnexion Kafka
    ↓
Si reconnexion réussie → réinjection des fichiers buffered → DELETE fichiers
```

**Invariant clé :** les fichiers CSV ne sont supprimés qu'après confirmation d'envoi Kafka (`offset committed`). Un crash du backend pendant la reprise = aucune perte (les fichiers CSV persistent).

### Implémentation

```python
# app/services/kafka_consumer.py

async def safe_produce(msg: dict, producer: AIOKafkaProducer) -> None:
    try:
        await producer.send_and_wait(settings.KAFKA_TOPIC_IOT, msg)
    except KafkaConnectionError:
        _buffer_to_disk(msg)   # CSV local → /tmp/kafka-buffer/

async def _replay_buffer(producer: AIOKafkaProducer) -> None:
    """Background task : toutes les 30s, rejoue les fichiers buffered."""
    for f in Path(settings.KAFKA_BUFFER_DIR).glob("*.csv"):
        msgs = _read_csv(f)
        for msg in msgs:
            await producer.send_and_wait(...)
        f.unlink()  # supprimé seulement après commit Kafka
```

**Dépendance :** bloqué par Sprint 7 (le producer Kafka doit exister).

---

## 4. US-34 — DAG Airflow réentraînement hebdomadaire

### Problème
Le modèle No-Show (Sprint 5) est entraîné une fois et servi statiquement. Les données de rendez-vous évoluent (saisons, nouveaux médecins, comportements patients) → le modèle dérive progressivement.

### Solution : Airflow DAG hebdomadaire

```
Chaque lundi 02h00 UTC
    ↓
DAG: retrain_noshow_weekly
    ↓
Task 1 : extract_data
  └─ SELECT * FROM appointments WHERE created_at >= NOW() - INTERVAL '4 weeks'
  └─ export CSV → /tmp/retrain/noshow_latest.csv
    ↓
Task 2 : run_training
  └─ PythonOperator → scripts/train_noshow.py --data /tmp/retrain/noshow_latest.csv
  └─ MLflow run enregistré automatiquement
    ↓
Task 3 : quality_gate
  └─ F1 ≥ 0.80 AND AUC ≥ 0.87 → passe
  └─ Sinon → XCom failure → Task 4 skipped
    ↓
Task 4 : promote_model  (si gate passe)
  └─ scripts/register_noshow_model.py --promote
  └─ Alias MLflow "champion" pointe vers la nouvelle version
    ↓
Task 5 : notify
  └─ Email/Slack : "Réentraînement réussi, F1=0.83, AUC=0.91, version N+1 en prod"
  └─ Log audit RGPD (actor=system, action=model_retrain)
```

### Fichier DAG (`dags/retrain_noshow_weekly.py`)

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "medisense-mlops",
    "retries": 1,
    "retry_delay": timedelta(minutes=15),
    "email_on_failure": True,
}

with DAG(
    dag_id="retrain_noshow_weekly",
    schedule_interval="0 2 * * 1",   # lundi 02h00 UTC
    start_date=datetime(2026, 7, 6),
    default_args=default_args,
    catchup=False,
    tags=["mlops", "no-show"],
) as dag:
    # ... tâches
```

**Réutilisation :** `scripts/train_noshow.py` et `scripts/register_noshow_model.py` (Sprint 6) sont appelés sans modification — Airflow est uniquement l'orchestrateur.

### Service docker-compose à ajouter

```yaml
airflow:
  image: apache/airflow:2.9-python3.12
  environment:
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/airflow_db
    AIRFLOW__CORE__DAGS_FOLDER: /opt/airflow/dags
    AIRFLOW__CORE__LOAD_EXAMPLES: "false"
  volumes:
    - ./dags:/opt/airflow/dags
    - ./backend/scripts:/opt/airflow/scripts
    - airflow_logs:/opt/airflow/logs
  ports:
    - "8080:8080"
  depends_on:
    postgres:
      condition: service_healthy
  command: >
    bash -c "airflow db migrate && airflow users create --username admin
    --password admin --role Admin --email admin@medisense.ai &&
    airflow webserver & airflow scheduler"
```

> Note : Airflow utilise une base `airflow_db` distincte sur le même PostgreSQL 16 (évite un nouveau service DB).

---

## 5. US-35 — Evidently AI : détection de dérive des données

### Problème
Le modèle No-Show est réentraîné sur les 4 dernières semaines. Mais si les données de production dérivent silencieusement (ex. nouvelle tranche d'âge de patients, changement de zone géographique), le modèle peut se dégrader sans que les métriques de training le détectent.

### Solution : Evidently AI — rapport PSI + feature importance shift

**Quand déclenchée :** après chaque réentraînement Airflow (Task 2.5 entre quality_gate et promote).

```python
# scripts/detect_drift.py

from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from evidently.metrics import ColumnDriftMetric

report = Report(metrics=[
    DataDriftPreset(),
    TargetDriftPreset(),
    ColumnDriftMetric(column_name="age_group"),
    ColumnDriftMetric(column_name="distance_km"),
    ColumnDriftMetric(column_name="appointment_type"),
])

# Référence = données d'entraînement précédentes (4 semaines N-1)
# Courant   = données d'entraînement actuelles (4 semaines N)
report.run(reference_data=df_reference, current_data=df_current)
report.save_html("results/drift_report_latest.html")
```

### Métriques suivies

| Métrique | Seuil d'alerte | Action |
|----------|:--------------:|--------|
| PSI global | > 0.25 | Email/Slack + log audit |
| PSI par feature (`age_group`, `distance_km`, `sms_consent`) | > 0.25 sur ≥ 2 features | Blocage promotion (US-36) |
| Feature importance shift (SHAP) | > 20% de changement | Avertissement |
| Target drift (taux no-show) | > 5 points % | Alerte critique |

**Interprétation PSI :**
- PSI < 0.1 : distribution stable, promotion sûre
- PSI ∈ [0.1, 0.25] : dérive modérée, surveiller
- PSI > 0.25 : dérive significative → bloquer promotion, investiguer

### Endpoint admin

```python
# GET /api/v1/admin/drift-report → retourne le rapport Evidently HTML comme pièce jointe
# Auth: require_admin
# Retourne le rapport de la dernière exécution détection_drift
```

---

## 6. US-36 — Auto-rollback modèle si F1 chute > 10%

### Problème
Un modèle promu peut se dégrader en production sur les premières 24h si le dataset de validation ne reflète pas exactement la distribution de production (edge cases récents, patients atypiques).

### Solution : Surveillance post-promotion + rollback MLflow

```
Modèle N promu en production (alias "champion" → version N)
    ↓
Feedback endpoint : POST /api/v1/predict/feedback
  └─ patient_id, prediction (0/1), actual_outcome (0/1)
  └─ INSERT noshow_feedback (Sprint 5)
    ↓
Monitoring F1 sur rolling 24h (Task Airflow: check_production_perf — toutes les 6h)
    ↓
F1 prod(N) < F1 prod(N-1) × 0.90  ?
    ↓ OUI
auto_rollback.py
  └─ version_n_minus_1 = _get_previous_version("noshow-risk-model")
  └─ client.set_registered_model_alias("noshow-risk-model", "champion", version_n_minus_1)
  └─ Email/Slack : "ROLLBACK automatique v{N} → v{N-1}. F1 prod: 0.71 < 0.78 × 0.90"
  └─ Log audit RGPD (actor=system, action=model_rollback)
```

### Implémentation (`scripts/auto_rollback.py`)

```python
from mlflow import MlflowClient

def auto_rollback_if_degraded(model_name: str, threshold: float = 0.10) -> bool:
    client = MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    # Trie par version DESC → v[0]=champion, v[1]=N-1
    sorted_versions = sorted(versions, key=lambda v: int(v.version), reverse=True)

    f1_current = _get_prod_f1(hours=24)
    f1_previous = float(sorted_versions[1].tags.get("f1_prod", 0))

    if f1_current < f1_previous * (1 - threshold):
        client.set_registered_model_alias(
            model_name, "champion", sorted_versions[1].version
        )
        return True   # rollback effectué
    return False
```

**Réutilisation :** l'alias `champion` est le même mécanisme que Sprint 6 (US-33). `noshow_predictor.py` charge toujours `mlflow.pyfunc.load_model("models:/noshow-risk-model@champion")` — le rollback est transparent pour l'endpoint `/predict`.

---

## 7. Infrastructure technique & artefacts prévus

### Services docker-compose à ajouter

| Service | Image | Port | Dépendance |
|---------|-------|:----:|-----------|
| `airflow` | `apache/airflow:2.9-python3.12` | 8080 | postgres (service_healthy) |
| `kafka` | `confluentinc/cp-kafka:7.6.1` | 9092 | — (Sprint 7) |

Services Prometheus + Grafana prévus en Sprint 10 (US-57).

### Dépendances Python à ajouter (`requirements.txt`)

```
apache-airflow[postgres]>=2.9.0   # DAG scheduler + LocalExecutor
evidently>=0.4.0                   # drift detection
```

### Variables `.env.example` à ajouter

```bash
# Airflow
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__CORE__FERNET_KEY=<générer: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Evidently
EVIDENTLY_PSI_THRESHOLD=0.25
EVIDENTLY_REPORT_DIR=results/drift_reports

# MLflow (déjà présents Sprint 6, rappel)
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_MODEL_NAME=noshow-risk-model
```

### Artefacts livrés

| Artefact | Description |
|----------|-------------|
| `results/drift_report_latest.html` | Rapport Evidently HTML (dernière exécution) |
| `results/rollback_log.json` | Historique des rollbacks automatiques |
| `dags/retrain_noshow_weekly.py` | DAG Airflow documenté |
| `scripts/detect_drift.py` | Script Evidently standalone |
| `scripts/auto_rollback.py` | Script rollback MLflow standalone |

---

## 8. Métriques cibles & validation

| Métrique | Cible | Méthode de mesure |
|----------|:-----:|-------------------|
| Uptime SLA service FastAPI | **≥ 99.5%** | Docker healthcheck + logs nginx |
| Zéro perte données IoT en mode dégradé Kafka | **0 msg perdu** | Test : couper Kafka 1h → vérifier replay complet |
| DAG Airflow s'exécute sans intervention | **100% runs** | Airflow UI → DAG history |
| Drift PSI détecté < 15 min après injection | **< 15 min** | Injecter distribution synthétique dérivée |
| Rollback déclenché et effectif | **< 30 min** | Simuler dégradation F1 → vérifier alias MLflow |
| Circuit breaker Salesforce distribué | **État cohérent multi-workers** | Lancer 2 workers uvicorn → vérifier Redis `cb:salesforce:state` |

---

## 9. Décisions d'architecture & leçons de conception

### D1 — Airflow LocalExecutor (pas CeleryExecutor)
**Raison :** Machine unique (VM clinique). CeleryExecutor nécessite un broker de tâches supplémentaire (RabbitMQ/Redis worker séparé). LocalExecutor est suffisant pour 1-2 DAGs hebdomadaires et s'intègre sur le PostgreSQL existant.

**Limite :** passage à CeleryExecutor si on monte à >10 DAGs ou si les DAGs durent >30 min (formation LSTM).

### D2 — Base `airflow_db` sur le même PostgreSQL 16 (pas un service DB séparé)
**Raison :** En dev/staging mono-machine, multiplier les services DB augmente la complexité opérationnelle sans bénéfice. En production, les deux bases sont sur le même PostgreSQL avec des rôles séparés.

### D3 — Rollback sur l'alias MLflow (pas sur les versions model stages)
**Raison :** Les stages MLflow (`Staging`, `Production`) sont dépréciés depuis MLflow 2.9. L'alias `champion` est l'API recommandée — cohérent avec Sprint 6 (US-33).

### D4 — Circuit breaker Salesforce vers Redis (Sprint 8 extension)
**Raison :** Le circuit breaker de Sprint 6 stocke l'état en mémoire processus. Avec `uvicorn --workers 4`, chaque worker a son propre état → un worker peut ouvrir le circuit tandis qu'un autre continue d'appeler Salesforce. Solution Sprint 8 : Redis hash `cb:salesforce:{state, failure_count, last_failure_at}`.

### D5 — PSI comme seuil de drift (pas KL-divergence)
**Raison :** PSI est interprétable opérationnellement (`< 0.1`, `0.1-0.25`, `> 0.25`) et calculé en O(n) sur les données binned. La KL-divergence est asymétrique et sensible aux bins vides — moins adapté pour des distributions de features cliniques.

---

## 10. Ce sur quoi te concentrer — Profil DS/IA

### Pour comprendre le sprint rapidement

1. **Lire `scripts/train_noshow.py`** — le DAG Airflow appelle ce script ; comprendre ses arguments CLI et son output (`noshow_training_report.json`) est essentiel pour US-34.
2. **Lire `scripts/register_noshow_model.py`** — comprendre l'alias `champion` et le mécanisme de promotion (réutilisé tel quel pour l'auto-rollback).
3. **Lire `app/services/noshow_predictor.py`** — voir comment le modèle est chargé via l'alias MLflow (`models:/noshow-risk-model@champion`) — le rollback est transparent pour ce service.

### Points d'attention DS/IA

- **Fenêtre de référence Evidently :** ne pas choisir une fenêtre trop courte (1 semaine) ou trop longue (6 mois). 4 semaines glissantes = compromis entre réactivité aux dérives récentes et stabilité statistique.
- **PSI sur features catégorielles :** `appointment_type` (consultation, urgence, suivi) peut avoir des bins déséquilibrés. Vérifier que les bins ne sont pas trop petits (< 5% de fréquence) avant de calculer le PSI — faux alertes sur bins rares.
- **Rollback conditionnel :** la condition `F1_prod(N) < F1_prod(N-1) × 0.90` suppose que F1 N-1 est stocké dans les tags MLflow du run précédent. Vérifier que `train_noshow.py` log bien `f1_prod` dans les tags MLflow (et non seulement dans les métriques de run).
- **Airflow idempotence :** le DAG doit être idempotent — si relancé manuellement après un échec partiel, il ne doit pas créer de doublons dans MLflow Registry ou dans la table `noshow_feedback`.
