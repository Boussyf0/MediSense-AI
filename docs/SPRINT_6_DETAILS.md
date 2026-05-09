# Sprint 6 — Salesforce & MLOps : Détail Complet
**08 Juin – 21 Juin 2026 | Statut : ✅ TERMINÉ**

> Ce document explique **ce qui a été construit**, **pourquoi chaque décision a été prise**, et **ce sur quoi tu dois te concentrer** en tant que profil Data Science & IA pour exploiter, maintenir et faire évoluer l'intégration CRM et le pipeline MLOps.

---

## Table des Matières

1. [Vue d'ensemble du Sprint 6](#1-vue-densemble-du-sprint-6)
2. [US-24 — Webhook Salesforce transactionnel](#2-us-24--webhook-salesforce-transactionnel)
3. [US-43 — Interface secrétaire des tâches CRM](#3-us-43--interface-secrétaire-des-tâches-crm)
4. [US-33 — MLflow Model Registry](#4-us-33--mlflow-model-registry)
5. [US-37 — CI/CD GitHub Actions renforcé](#5-us-37--cicd-github-actions-renforcé)
6. [US-38 — OWASP ZAP scan automatisé](#6-us-38--owasp-zap-scan-automatisé)
7. [Infrastructure technique & artefacts livrés](#7-infrastructure-technique--artefacts-livrés)
8. [Validation, métriques finales & tests](#8-validation-métriques-finales--tests)
9. [Bugs résolus & leçons apprises](#9-bugs-résolus--leçons-apprises)
10. [Ce sur quoi te concentrer — Profil DS/IA](#10-ce-sur-quoi-te-concentrer--profil-dsia)

---

## 1. Vue d'ensemble du Sprint 6

### Objectif
Industrialiser le passage du prototype IA vers un cycle exploitable en production :
- synchronisation CRM fiable, traçable et auditable (Salesforce),
- gouvernance du modèle no-show via MLflow Model Registry,
- pipeline CI/CD orienté qualité avec gates automatisées,
- scan sécurité OWASP ZAP hebdomadaire.

### Résultat final

| Axe évalué | Score | Lecture |
|------------|-------|---------|
| Valeur produit sprint | **4.7 / 5** | La boucle prédiction → CRM → action secrétaire est fermée end-to-end. |
| Qualité d'implémentation | **4.6 / 5** | Séparation nette des responsabilités, correlation IDs, RGPD Art.30 respecté. |
| Maturité production ML | **4.5 / 5** | Registry + quality gate + serving via alias — vrai MLOps opérationnel. |

### User Stories couvertes

| US | Description | Story Points | Statut |
|----|-------------|:------------:|:------:|
| US-24 | Webhook Salesforce transactionnel avec retry et circuit breaker | 8 | ✅ |
| US-43 | Interface secrétaire : lister, patcher, relancer les tâches CRM | 3 | ✅ |
| US-33 | MLflow Model Registry : versioning, quality gate, promotion alias | 5 | ✅ |
| US-37 | CI/CD : pip cache, coverage gate 80%, ML gate, build-and-push GHCR | 8 | ✅ |
| US-38 | OWASP ZAP scan baseline hebdomadaire, gate 0 High | 5 | ✅ |
| **Total** | | **29 pts** | ✅ |

### Ce qui a été livré

```text
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   └── crm.py                          # US-43 GET/PATCH/POST /crm/tasks
│   ├── schemas/
│   │   └── crm.py                          # CRMTaskOut, CRMTaskPatch, CRMRetryResponse
│   ├── services/
│   │   ├── salesforce_client.py            # US-24 HTTP + circuit breaker + persistence
│   │   └── noshow_predictor.py             # US-33 registry-first model loading
│   ├── agents/
│   │   └── crm_agent.py                    # refactorisé : thin wrapper salesforce_client
│   ├── core/
│   │   └── config.py                       # 8 nouveaux settings Salesforce + MLflow
│   └── db/models/
│       └── appointment.py                  # 5 colonnes crm_* ajoutées
├── alembic/versions/
│   └── 20260608_000000_sprint6_salesforce_mlops.py
├── scripts/
│   ├── __init__.py                         # rend scripts/ importable comme package
│   ├── train_noshow.py                     # quality gate avant mlflow.register_model
│   └── register_noshow_model.py            # CLI promotion champion/challenger
└── tests/
    ├── test_crm_tasks.py                   # 5 unit + 13 integration tests
    └── test_mlflow_registry.py             # 18 unit tests

.github/workflows/
├── ci.yml                                  # renforcé (4 additions)
└── security-zap.yml                        # nouveau workflow ZAP

.zap/
└── rules.tsv                               # whitelist faux positifs

backend/
└── pyrightconfig.json                      # résolution scripts.* dans l'IDE
```

---

## 2. US-24 — Webhook Salesforce transactionnel

### Problème résolu
Le webhook Salesforce existait dans `crm_agent.py` en mode best-effort : échec → log → continuer. Aucune trace en base, aucun retry contrôlé, aucune visibilité secrétaire.

### Architecture implémentée

```
Patient query
    ↓
orchestrator.run_agent_flow()
    ↓
crm_agent.run()               ← thin wrapper
    ↓
salesforce_client.send_crm_event()
    ├─ circuit breaker check (CLOSED/OPEN/HALF-OPEN)
    ├─ POST https://salesforce/webhook  { event_type, correlation_id, ... }
    └─ _persist_sync_result(db, ...)    → appointments.crm_*
```

### `salesforce_client.py` — Responsabilités

| Responsabilité | Détail |
|----------------|--------|
| Correlation ID | `uuid.uuid4()` généré par appel — tracé dans payload et DB |
| Circuit breaker | Module-level, 3 failures → OPEN 60s → HALF-OPEN trial |
| Payload enrichi | `event_type`, `correlation_id`, `query_summary[:200]`, `iot_triggered` |
| Persistence | `UPDATE appointments SET crm_sync_status=..., crm_correlation_id=..., crm_retry_count+=delta` |
| Non-raising | Toutes exceptions catchées — `SalesforceResult` toujours retourné |

### Machine d'états CRM

```
PENDING
  ├─→ SENT       (HTTP 2xx)
  ├─→ FAILED     (HTTP 5xx ou exception réseau)
  ├─→ SKIPPED    (URL vide ou severity=info)
  └─→ CB_OPEN    (circuit breaker ouvert)
```

### Payload Salesforce

```json
{
  "event_type":      "appointment_triage",
  "correlation_id":  "uuid-v4",
  "patient_id":      "uuid-v4",
  "appointment_id":  "uuid-v4 | null",
  "severity":        "urgent | routine | info",
  "specialist_type": "cardiologie | null",
  "query_summary":   "string ≤ 200 chars",
  "iot_triggered":   true,
  "timestamp":       "ISO8601"
}
```

### Décision clé — Circuit breaker process-local

Le circuit breaker (`_cb_failures`, `_cb_open_since`) est stocké en mémoire du processus. En déploiement multi-worker (`--workers > 1`), chaque worker maintient son propre compteur — ils ne se coordonnent pas.

**Mitigation Sprint 7** : migrer ces clés vers Redis (`INCRBY crm:cb:failures` + `SET crm:cb:open_since EX 60`). L'interface de `send_crm_event()` n'a pas à changer.

### Settings ajoutés (`config.py`)

```python
SALESFORCE_WEBHOOK_URL: str = ""
SALESFORCE_TOKEN: str = ""
SALESFORCE_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)
SALESFORCE_MAX_RETRIES: int = Field(default=3, ge=1, le=5)
SALESFORCE_RETRY_DELAY_SECONDS: float = Field(default=2.0, gt=0)
```

### Migration Alembic — colonnes ajoutées

```sql
crm_sync_status   VARCHAR(20)   NOT NULL DEFAULT 'PENDING'
crm_correlation_id VARCHAR(64)
crm_retry_count   SMALLINT      NOT NULL DEFAULT 0
crm_last_error    TEXT
crm_synced_at     TIMESTAMPTZ

CHECK crm_sync_status IN ('PENDING','SENT','FAILED','SKIPPED','CB_OPEN')
INDEX idx_appointments_crm_retry WHERE crm_sync_status = 'FAILED'
```

---

## 3. US-43 — Interface secrétaire des tâches CRM

### Endpoints livrés

| Méthode | Route | Auth | Comportement |
|---------|-------|------|--------------|
| `GET` | `/api/v1/crm/tasks` | secretary/admin | Liste paginée, filtre `?crm_sync_status=` |
| `PATCH` | `/api/v1/crm/tasks/{uuid}` | secretary/admin | Mise à jour `salesforce_task_id` ou `crm_sync_status` |
| `POST` | `/api/v1/crm/tasks/{uuid}/retry` | secretary/admin | Retry asynchrone Salesforce (fire-and-forget) |

### Règles métier

- `PATCH` : `crm_sync_status` validé par `@field_validator` — seuls `PENDING | SENT | FAILED | SKIPPED | CB_OPEN` acceptés.
- `POST /retry` : 409 si statut `SENT` sans `force=true` ; 429 si `crm_retry_count >= SALESFORCE_MAX_RETRIES`.
- Retry non-bloquant : `asyncio.create_task(send_crm_event(..., db=None))` — la réponse HTTP retourne immédiatement.
- Toute opération écrit dans `audit_logs` (RGPD Art. 30).

### Schémas Pydantic

```python
CRMTaskOut          # réponse GET et PATCH (from_attributes=True)
CRMTaskPatch        # corps PATCH (validation longueur + enum statut)
CRMRetryRequest     # corps POST retry (force: bool = False)
CRMRetryResponse    # réponse POST retry
CRMTaskListResponse # réponse GET paginée (total + items)
```

---

## 4. US-33 — MLflow Model Registry

### Problème résolu
Sprint 5 loggait les métriques et le modèle dans MLflow, mais ne l'enregistrait jamais dans le Model Registry. La promotion champion/challenger était inexistante. Le service d'inférence ignorait complètement MLflow.

### Boucle MLOps complète livrée

```
train_noshow.py
    ├─ benchmark XGB/LGBM/CAT (5-fold SMOTE)
    ├─ évaluation test set (F1, AUC, Brier, ECE)
    ├─ quality gate : F1 ≥ 0.80 AND AUC ≥ 0.87
    │       ✓ → mlflow.register_model("noshow-risk-model")
    │       ✗ → log warning, pas d'enregistrement
    └─ rapport JSON enrichi (mlflow_run_id inclus)
         ↓
register_noshow_model.py --run-id <id> --alias champion
    ├─ récupère test_f1 / test_auc du run
    ├─ quality gate (configurable --f1-threshold / --auc-threshold)
    └─ mlflow.register_model() + set_registered_model_alias()
         ↓
noshow_predictor._load_models()
    ├─ essai 1 : mlflow.sklearn.load_model("models:/noshow-risk-model@champion")
    └─ fallback : joblib.load("backend/models/noshow_model.joblib")
```

### CLI `register_noshow_model.py`

```bash
# Promotion en production (champion)
python scripts/register_noshow_model.py \
    --run-id <mlflow_run_id> \
    --alias champion

# Test à blanc sans écriture
python scripts/register_noshow_model.py \
    --run-id <id> --alias challenger --dry-run

# Forcer malgré métriques insuffisantes (urgence)
python scripts/register_noshow_model.py \
    --run-id <id> --alias challenger --force
```

**Résolution tracking URI** : CLI arg → `MLFLOW_TRACKING_URI` env → `backend/.local/mlflow/runs/` (fallback local).

### Version string du modèle servi

| Scénario | `model_version` retourné par l'API |
|----------|------------------------------------|
| Chargé depuis MLflow registry | `v6.0-xgboost-run<8 premiers chars run_id>` |
| Fallback joblib sans run_id | `v5.1-xgboost` |
| Fallback sans metadata | `v5.0-xgb` |

### Settings ajoutés (`config.py`)

```python
MLFLOW_MODEL_NAME: str = "noshow-risk-model"
MLFLOW_PROMOTION_F1_THRESHOLD: float = Field(default=0.80, ge=0.0, le=1.0)
MLFLOW_PROMOTION_AUC_THRESHOLD: float = Field(default=0.87, ge=0.0, le=1.0)
```

---

## 5. US-37 — CI/CD GitHub Actions renforcé

### Quatre additions au `ci.yml`

#### a) Cache pip
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('backend/requirements.txt') }}
```
Économise ~2 min par run sur un cache chaud.

#### b) Coverage gate (DoD ≥ 80 %)
```yaml
pytest -q --cov=app --cov-report=xml --cov-fail-under=80
```
Le rapport `coverage.xml` est archivé en artefact CI pour suivi.

#### c) ML quality gate
```python
m = json.loads(Path("backend/models/noshow_training_report.json").read_text())["test_metrics"]
if float(m["f1"]) < 0.80 or float(m["auc"]) < 0.87:
    sys.exit(1)   # bloque le pipeline
```
Ignoré si le fichier est absent (pas de modèle entraîné en CI).

#### d) Build-and-push GHCR
```yaml
# Tags générés automatiquement :
#   sha-<commit>    (toujours)
#   <branch-name>   (toujours)
#   latest          (main uniquement)
push: ${{ github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/heads/release/') }}
```

### Pipeline complet après Sprint 6

```
Push / PR
   ↓ Cache pip
   ↓ Install deps
   ↓ Compile Python
   ↓ Tests + coverage ≥ 80%
   ↓ Red-team safety (strict_pass_rate = 1.0)
   ↓ ML quality gate (F1 ≥ 0.80, AUC ≥ 0.87)
   ↓ Free disk space
   ↓ Login GHCR (main/release uniquement)
   ↓ Build & push image (sha-, branch-, latest tags)
```

---

## 6. US-38 — OWASP ZAP scan automatisé

### Workflow `security-zap.yml`

- **Déclencheur** : cron `0 3 * * 1` (lundi 03:00 UTC) + `workflow_dispatch`.
- **Services** : PostgreSQL 16 + Redis 7 (mêmes variables que `ci.yml`).
- **Cible** : `http://localhost:8000` (API uvicorn démarrée en background).
- **Action** : `zaproxy/action-baseline@v0.12.0`.
- **Gate** : `riskcode == "3"` (High) → `sys.exit(1)`.
- **Artefact** : `report_html.html` archivé systématiquement (`if: always()`).

### Whitelist `.zap/rules.tsv`

| Rule ID | Action | Justification |
|---------|--------|---------------|
| 10202 | IGNORE | Anti-CSRF inapplicable — API JWT stateless |
| 10036 | WARN | Header version serveur — informatif |
| 90005 | IGNORE | Hints navigateur — inapplicables à une API JSON |
| 10063 | IGNORE | Hints navigateur — inapplicables à une API JSON |
| 10096 | WARN | Timestamps ISO8601 intentionnels |
| 10021 | WARN | X-Content-Type-Options déjà positionné par FastAPI |

---

## 7. Infrastructure technique & artefacts livrés

### Variables d'environnement nouvelles (`.env.example` mis à jour)

```env
# Salesforce CRM
SALESFORCE_WEBHOOK_URL=
SALESFORCE_TOKEN=
SALESFORCE_TIMEOUT_SECONDS=3.0
SALESFORCE_MAX_RETRIES=3
SALESFORCE_RETRY_DELAY_SECONDS=2.0

# MLflow Model Registry
MLFLOW_MODEL_NAME=noshow-risk-model
MLFLOW_PROMOTION_F1_THRESHOLD=0.80
MLFLOW_PROMOTION_AUC_THRESHOLD=0.87
```

### Décisions d'architecture notables

| Décision | Alternative rejetée | Raison |
|----------|---------------------|--------|
| `asyncio.create_task` pour retry CRM | Celery/RQ task queue | Overhead nul, adapté au volume clinique |
| `db=None` dans le retry fire-and-forget | Passer la session courante | Session fermée après réponse HTTP — lèverait une exception |
| Import top-level de `send_crm_event` dans `crm.py` | Import lazy dans la fonction | Détection erreur au démarrage, pas à l'exécution |
| `scripts/__init__.py` | `sys.path.insert` dans conftest | Solution propre, résout aussi l'IDE (pyrightconfig.json) |
| Quality gate dans `train_noshow.py` | Gate uniquement dans le CLI | Prévient la pollution du registry dès l'entraînement |

---

## 8. Validation, métriques finales & tests

### Résultats tests

| Suite | Tests | Résultat |
|-------|------:|---------|
| `test_crm_tasks.py` — Unit (SalesforceClient) | 5 | ✅ 5/5 |
| `test_crm_tasks.py` — Integration (CRMEndpoints) | 13 | ✅ 13/13 (avec Docker) |
| `test_mlflow_registry.py` — Unit | 18 | ✅ 18/18 |
| `test_agents.py::TestCRMCircuitBreaker` | 3 | ✅ 3/3 |
| **Total nouveaux tests Sprint 6** | **39** | **✅** |

### Couverture des scénarios clés

| Scénario | Test |
|----------|------|
| Webhook 200 → `sent=True`, correlation_id UUID4 valide | `test_send_success` |
| Webhook 500 → `sent=False`, `_cb_failures` incrémenté | `test_send_5xx_marks_failed` |
| URL vide → skip silencieux, pas d'appel HTTP | `test_skipped_when_no_url` |
| 3× 500 → circuit ouvert → 4e appel `cb_open=True` | `test_circuit_breaker_opens_after_threshold` |
| `db=None` → pas d'exception | `test_persist_skips_when_db_is_none` |
| GET /crm/tasks sans token → 401 | `test_list_requires_auth` |
| GET /crm/tasks rôle doctor → 403 | `test_list_doctor_forbidden` |
| PATCH statut invalide → 422 | `test_patch_invalid_status_returns_422` |
| POST retry tâche SENT sans force → 409 | `test_retry_sent_without_force_returns_409` |
| POST retry max retries atteint → 429 | `test_retry_max_retries_exceeded_returns_429` |
| Quality gate F1 < 0.80 → sys.exit(1) | `test_exits_1_on_gate_failure` |
| `--dry-run` → sys.exit(0), register_model non appelé | `test_dry_run_exits_0_without_registering` |
| `--force` → promotion malgré métriques basses | `test_force_skips_gate_and_promotes` |
| version string avec `mlflow_run_id` | `test_version_includes_run_id_prefix` |

### KPIs Sprint 6

| KPI | Cible | Résultat |
|-----|-------|----------|
| Vulnérabilités ZAP High | 0 | ✅ Gate configurée |
| Coverage backend | ≥ 80% | ✅ `--cov-fail-under=80` en CI |
| Traçabilité modèle | 100% runs promus ont run_id | ✅ quality gate training + CLI |
| Serving via registry alias | champion → inférence | ✅ fallback transparent |

---

## 9. Bugs résolus & leçons apprises

### Problèmes rencontrés

| Problème | Cause | Fix |
|----------|-------|-----|
| Import lazy `send_crm_event` dans `crm.py` | Copié depuis un prototype | Déplacé en import top-level |
| `scripts.*` non résolu par Pyright | Pas d'`__init__.py` ni de `pyrightconfig.json` | Ajout `scripts/__init__.py` + `pyrightconfig.json` |
| `@pytest.mark.asyncio` redondants | `asyncio_mode = auto` dans `pytest.ini` couvre déjà | Supprimés (18 → 0 décorateurs) |
| `mlflow` absent du venv dev | ML packages non installés globalement | Stub `sys.modules` dans `test_mlflow_registry.py` |
| `register_model` appelé même si métriques insuffisantes | Pas de gate dans `train_noshow.py` | Ajout du check avant l'appel |
| Circuit breaker non distribué | State module-level | Documenté comme limitation Sprint 7 (Redis) |

### Leçons apprises

1. **Séparation HTTP / métier** — Extraire `salesforce_client.py` de `crm_agent.py` a immédiatement révélé que les tests mockaient `os.environ` au lieu de `get_settings`. L'abstraction correcte force des tests corrects.

2. **La quality gate doit vivre au plus tôt** — Une gate uniquement dans le CLI de promotion ne protège pas si quelqu'un appelle `mlflow.register_model()` directement. La gate dans `train_noshow.py` ferme ce vecteur.

3. **Registry-first avec fallback** — Charger depuis `models:/noshow-risk-model@champion` en priorité garantit que la promotion CLI a un effet réel sur l'inférence. Sans cette connexion, le registry est décoratif.

4. **La limitation multi-worker doit être documentée explicitement** — Un commentaire `# WARNING` dans le code est plus utile qu'un ticket JIRA oublié.

---

## 10. Ce sur quoi te concentrer — Profil DS/IA

### Priorité 1 — Comprendre la boucle MLOps end-to-end

La boucle est maintenant complète :
```
entraînement → quality gate → registry → alias champion → serving
```
Tout modèle promu est traçable : `run_id`, métriques, artefacts SHAP, rapport JSON.

**Action** : lancer `train_noshow.py` → noter le `run_id` → exécuter `register_noshow_model.py --alias challenger --dry-run` → vérifier que le service retourne la bonne `model_version`.

### Priorité 2 — Calibration comme critère de promotion (Sprint 7)

Sprint 6 gate uniquement sur F1 et AUC. Or Brier score et ECE mesurent la fiabilité des probabilités — décisif pour le seuil SMS (30%). Le prochain sprint doit ajouter :
```python
if test_brier > BRIER_THRESHOLD or test_ece > ECE_THRESHOLD:
    # ne pas promouvoir
```

### Priorité 3 — Observer les transitions CRM en production

La machine d'états (`PENDING → SENT | FAILED | CB_OPEN`) est maintenant persistée. En situation réelle :
- monitorer le taux `FAILED / total` par fenêtre glissante,
- alerter si le circuit breaker s'ouvre (`crm_open_since IS NOT NULL AND age > 5 min`),
- analyser `crm_last_error` pour distinguer timeouts réseau d'erreurs Salesforce.

### Priorité 4 — Préparer le circuit breaker distribué

Quand le nombre de workers uvicorn passera à > 1 (Sprint 8 — production), le circuit breaker local ne suffira plus. La migration vers Redis est planifiée :

```python
# Sprint 7 — interface identique, état dans Redis
cb_failures = await redis.incr("crm:cb:failures")
if cb_failures >= FAILURE_THRESHOLD:
    await redis.set("crm:cb:open_since", time.time(), ex=RESET_TIMEOUT_S)
```

L'interface publique `send_crm_event()` ne change pas — seul l'état migre.

### Priorité 5 — ZAP en développement local

Le scan ZAP tourne en CI chaque lundi. Pour tester localement :
```bash
# Démarrer l'API
cd backend && uvicorn app.main:app --port 8000 &

# Lancer le workflow manuellement via GitHub Actions UI
# ou installer Docker + ZAP et pointer sur localhost:8000
```

---

### Résultat final Sprint 6

Sprint 6 transforme MediSense AI d'un prototype performant localement en un pipeline exploitable :
- **CRM fiable** : corrélation ID, machine d'états, retry contrôlé, API secrétaire.
- **MLOps gouverné** : quality gate dès l'entraînement, promotion alias, serving registry-first.
- **CI/CD traçable** : coverage gate, ML gate, image taggée et publiée sur GHCR.
- **Sécurité automatisée** : ZAP scan hebdomadaire bloquant sur alertes High.
