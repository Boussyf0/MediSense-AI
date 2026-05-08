# Sprint 6 — Salesforce & MLOps : Détail Complet
**08 Juin – 21 Juin 2026 | Statut : ⏳ À VENIR (Blueprint d'exécution)**

> Ce document suit le format des précédents sprints, mais en mode **plan opérationnel détaillé**: il décrit l'existant, les écarts à combler, les livrables cibles, les métriques attendues et les risques à maîtriser pour Sprint 6.

---

## Table des Matières

1. [Vue d'ensemble du Sprint 6](#1-vue-densemble-du-sprint-6)
2. [US-24 — Webhook Salesforce transactionnel](#2-us-24--webhook-salesforce-transactionnel)
3. [US-43 — Interface secrétaire des tâches Salesforce](#3-us-43--interface-secrétaire-des-tâches-salesforce)
4. [US-33 — MLflow Model Registry](#4-us-33--mlflow-model-registry)
5. [US-37 — CI/CD GitHub Actions](#5-us-37--cicd-github-actions)
6. [US-38 — OWASP ZAP scan automatisé](#6-us-38--owasp-zap-scan-automatisé)
7. [Infrastructure technique & artefacts Sprint 6](#7-infrastructure-technique--artefacts-sprint-6)
8. [Validation, KPIs cibles & stratégie de tests](#8-validation-kpis-cibles--stratégie-de-tests)
9. [Risques projet & plan de mitigation](#9-risques-projet--plan-de-mitigation)
10. [Ce sur quoi te concentrer — Profil DS/IA](#10-ce-sur-quoi-te-concentrer--profil-dsia)

---

## 1. Vue d'ensemble du Sprint 6

### Objectif
Industrialiser le passage du prototype IA vers un cycle exploitable en production:
- synchronisation fiable avec le CRM (Salesforce),
- gouvernance du modèle no-show (registry/versioning),
- pipeline CI/CD orienté qualité + sécurité,
- scan sécurité automatisé avant livraison.

### User Stories prévues

| US | Description | Story Points | Priorité |
|----|-------------|:------------:|:--------:|
| US-24 | Webhook Salesforce Apex : tâche secrétaire créée automatiquement | 8 | Should |
| US-33 | MLflow Model Registry : versioning + métriques + artefacts SHAP | 5 | Should |
| US-37 | GitHub Actions CI/CD : build → test → push image → deploy | 8 | Should |
| US-38 | OWASP ZAP scan automatisé (rapport vulnérabilités) | 5 | Could |
| US-43 | Interface secrétaire : gestion tâches Salesforce (confirmer, clôturer) | 3 | Could |
| **Total** | | **29 pts** | |

### Baseline déjà disponible (avant Sprint 6)

| Élément | Déjà présent | Limite actuelle |
|--------|---------------|-----------------|
| CRM webhook | `backend/app/agents/crm_agent.py` (timeout + circuit breaker) | non persisté côté DB, pas d'API de suivi secrétaire |
| Donnée CRM | `appointments.salesforce_task_id` | pas de statut sync, pas de retry explicite |
| MLOps | `train_noshow.py` loggue dans MLflow (`backend/.local/mlflow/runs`) | pas de registration dans Model Registry |
| CI | `.github/workflows/ci.yml` compile/test/red-team/docker build | pas de release pipeline structuré ni gates de déploiement |
| Sécurité | red-team IA déjà en CI | pas de scan OWASP ZAP automatisé des endpoints API |

### KPI cibles Sprint 6

| KPI | Cible |
|-----|-------|
| Taux succès sync Salesforce | ≥ 99% (hors indispo réseau) |
| Temps webhook Salesforce P95 | < 1.5s |
| Temps pipeline CI (PR) | < 12 min |
| Vulnérabilités ZAP High | 0 |
| MTTR rollback pipeline CI/CD | < 10 min |
| Traçabilité modèle | 100% des modèles promus ont run_id + artefacts + métriques |

---

## 2. US-24 — Webhook Salesforce transactionnel

### Problème
Le webhook Salesforce existe déjà côté agent, mais il est aujourd'hui **best effort**: en cas d'échec, on loggue et on continue. C'est bon pour la résilience chat, insuffisant pour le pilotage opérationnel du secrétariat.

### Cible Sprint 6
Mettre en place un flux CRM robuste et auditable:
1. envoi webhook asynchrone avec corrélation d'ID,
2. persistance de l'état de synchronisation dans `appointments`,
3. retry contrôlé avec backoff et limite stricte,
4. visibilité API pour l'équipe secrétaire.

### Contrat payload recommandé

```json
{
  "event_type": "appointment_triage",
  "correlation_id": "uuid-v4",
  "patient_id": "uuid-v4",
  "appointment_id": "uuid-v4|null",
  "severity": "urgent|routine|info",
  "specialist_type": "cardiologie|null",
  "query_summary": "string<=200",
  "iot_triggered": true,
  "timestamp": "ISO8601"
}
```

### Évolution technique attendue
- déplacer la config Salesforce dans `Settings` (au lieu de `os.getenv()` dispersé),
- ajouter un service dédié `salesforce_client.py` (single responsibility),
- enrichir `appointments` avec statut sync + retry + message erreur,
- journaliser les transitions d'état pour post-mortem.

### États de synchronisation suggérés
- `NOT_SENT`
- `SENT`
- `ACKED`
- `FAILED_RETRYABLE`
- `FAILED_FINAL`

---

## 3. US-43 — Interface secrétaire des tâches Salesforce

### Problème
`salesforce_task_id` existe en base, mais aucune API ne permet à la secrétaire de:
- lister les tâches CRM en attente,
- confirmer un RDV,
- clôturer une action,
- voir l'historique d'échec sync.

### Cible API (backend)

| Endpoint | Rôle | But |
|----------|------|-----|
| `GET /api/v1/crm/tasks` | secretary/admin | lister tâches CRM avec filtres (`status`, `doctor_uuid`, `date`) |
| `PATCH /api/v1/crm/tasks/{appointment_uuid}` | secretary/admin | mettre à jour le statut métier (`confirmed`, `done`, `cancelled`) |
| `POST /api/v1/crm/tasks/{appointment_uuid}/resync` | secretary/admin | forcer une nouvelle tentative Salesforce |

### Règles métier
1. Pas de transition illégale (`DONE -> PENDING` interdit).
2. Toute modification écrit une trace d'audit.
3. Retourner un message explicite si `salesforce_task_id` est absent.
4. RBAC strict (`doctor`/`patient` interdits).

### Schémas recommandés
- `CRMTaskOut`
- `CRMTaskListOut`
- `CRMTaskUpdateIn`
- `CRMResyncOut`

---

## 4. US-33 — MLflow Model Registry

### État actuel
Le script `backend/scripts/train_noshow.py`:
- loggue params/métriques dans MLflow,
- loggue le modèle (`mlflow.sklearn.log_model`),
- loggue le rapport JSON.

Ce qui manque pour Sprint 6:
- registration formelle d'un modèle nommé,
- gestion des versions (v1, v2, ...),
- politique de promotion (staging/production),
- lien explicite entre modèle promu et seuils métier.

### Cible Sprint 6

#### Modèle registry proposé
- **Registered model name**: `noshow-risk-model`
- **Alias**:
  - `champion` (production)
  - `challenger` (candidate)
- **Tags minimaux**:
  - `data_version`
  - `feature_set_hash`
  - `owner`
  - `sprint`

#### Politique de promotion recommandée
Un modèle peut passer `challenger -> champion` si:
1. `test_f1 >= 0.80`
2. `test_auc >= 0.87`
3. `test_brier` et `test_ece` non dégradés au-delà d'un seuil défini
4. red-team safety inchangé en strict pass

### Livraison attendue
- script de registration/promotion explicite,
- document d'exploitation (`how to promote/revert`),
- endpoint de lecture version modèle active (transparence produit).

---

## 5. US-37 — CI/CD GitHub Actions

### État actuel
Le workflow `ci.yml` couvre déjà:
- checkout,
- install dépendances,
- compile Python,
- tests backend,
- red-team safety smoke + gate strict,
- docker build smoke.

### Cible Sprint 6
Passer d'une CI technique à une CI/CD exploitable:

```text
PR / Push
   ↓
quality-gates (lint/compile/tests/red-team)
   ↓
build-image (tag sha + branch)
   ↓
security-gates (OWASP ZAP baseline)
   ↓
publish (registry image)
   ↓
deploy (staging puis prod contrôlée)
```

### Conditions de blocage recommandées
- tests backend non passants,
- red-team strict < 100%,
- ZAP High > 0,
- artefact modèle absent sur release.

### Stratégie de branches
Conserver le déclenchement actuel:
- `main`
- `sprint/**`
- `release/**`

Et ajouter des environnements protégés GitHub:
- `staging` (auto),
- `production` (approval manuel).

---

## 6. US-38 — OWASP ZAP scan automatisé

### Objectif
Ajouter un filet sécurité AppSec systématique avant publication image/déploiement.

### Cible Sprint 6
- job `zap-baseline` en GitHub Actions,
- scan des endpoints API exposés (`/api/v1/**`),
- export rapport HTML + JSON en artefact CI,
- gate bloquante sur alertes High (et éventuellement Medium selon tolérance).

### Exécution type

```text
Start API test target
   ↓
Run ZAP baseline
   ↓
Publish report artifact
   ↓
Fail pipeline on severity policy breach
```

### Points de vigilance
- whitelister les faux positifs connus (fichier baseline),
- éviter que ZAP scanne un endpoint non prêt (healthcheck préalable),
- figer l'URL de cible pour reproductibilité.

---

## 7. Infrastructure technique & artefacts Sprint 6

### Arborescence cible (proposée)

```text
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   └── crm.py                         # US-43 API secrétaire CRM
│   ├── schemas/
│   │   └── crm.py                         # schémas Pydantic CRM
│   ├── services/
│   │   └── salesforce_client.py           # US-24 client webhook + retry
│   ├── core/
│   │   └── config.py                      # SALESFORCE_* + MLFLOW_* settings
│   └── db/models/
│       └── appointment.py                 # états sync CRM enrichis
├── alembic/versions/
│   └── 20260608_000000_sprint6_salesforce_mlops.py
├── scripts/
│   └── register_noshow_model.py           # US-33 registry/promotion
└── tests/
    ├── test_crm_tasks.py                  # US-24/US-43
    └── test_mlflow_registry.py            # US-33

.github/workflows/
├── ci.yml                                  # renforcé (gates)
└── security-zap.yml                        # US-38 scan OWASP
```

### Variables d'environnement à ajouter
- `SALESFORCE_WEBHOOK_URL`
- `SALESFORCE_TOKEN`
- `SALESFORCE_TIMEOUT_SECONDS`
- `SALESFORCE_MAX_RETRIES`
- `MLFLOW_TRACKING_URI`
- `MLFLOW_REGISTRY_URI`
- `MLFLOW_REGISTERED_MODEL_NAME`

---

## 8. Validation, KPIs cibles & stratégie de tests

### Matrice de validation Sprint 6

| Surface | Test attendu | Critère de succès |
|---------|--------------|-------------------|
| CRM webhook | tests unitaires retry + circuit breaker | transitions d'état exactes |
| API secrétaire CRM | tests RBAC + transitions statut | `secretary/admin` OK, autres `403` |
| MLflow registry | test script promotion | version enregistrée + alias défini |
| CI/CD | exécution workflow sur PR | artefacts générés + gates appliquées |
| ZAP | scan baseline | 0 High, rapport archivé |

### Jeux de tests à inclure
1. **Unit tests**: client Salesforce, rules de transition, policy promotion modèle.
2. **Integration tests**: endpoint CRM + DB + mock Salesforce.
3. **Security tests**: ZAP baseline en pipeline + assertions sur seuils.
4. **Non-régression**: tests Sprint 4/5 existants inchangés.

---

## 9. Risques projet & plan de mitigation

| Risque | Impact | Mitigation Sprint 6 |
|--------|--------|---------------------|
| Indisponibilité Salesforce | tâches non synchronisées | circuit breaker + retry + queue de resync |
| Promotion modèle non maîtrisée | régression no-show en prod | policy de promotion + rollback champion |
| Pipeline CI trop lent | feedback dev dégradé | paralléliser jobs + cache dépendances |
| Faux positifs ZAP | bruit opérationnel | baseline contrôlée + revue sécurité hebdo |
| Dette de configuration env | incidents déploiement | centraliser settings + `.env.example` à jour |

---

## 10. Ce sur quoi te concentrer — Profil DS/IA

### Priorité 1 — Gouvernance du modèle (US-33)
Ton enjeu principal n'est plus seulement de "faire un bon score", mais de garantir:
- traçabilité complète run -> modèle -> version déployée,
- reproductibilité (features, dataset, seed, hyperparams),
- critères de promotion alignés aux coûts métier.

### Priorité 2 — Coupler modèle et opérations CRM (US-24/43)
La valeur produit se matérialise quand la prédiction devient action secrétariat.  
Vérifie que la boucle est complète:
`prediction -> task CRM -> action humaine -> retour terrain`.

### Priorité 3 — Calibration continue
Sprint 5 a introduit Brier/ECE. Sprint 6 doit les utiliser comme **gates de promotion** plutôt que simples métriques observées.

### Priorité 4 — Sécurité by default
Le pipeline IA est désormais couplé à CI/CD. Les scans ZAP et gates red-team doivent rester bloquants pour éviter la dérive "shipping over safety".

---

### Résultat attendu en fin de Sprint 6
Un sprint est considéré réussi si MediSense passe d'un modèle performant localement à un flux exploitable en conditions réelles:
- action CRM fiable,
- versionnement modèle gouverné,
- pipeline CI/CD traçable,
- sécurité automatisée avant livraison.
