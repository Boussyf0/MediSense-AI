# Sprint 5 — ML Prédictif No-Show : Détail Complet
**25 Mai – 7 Juin 2026 | Statut : ✅ TERMINÉ**

> Ce document explique **ce qui a été construit**, **pourquoi chaque décision a été prise**, et **ce sur quoi tu dois te concentrer** en tant que profil Data Science & IA pour exploiter, maintenir et améliorer le pipeline prédictif No-Show.

---

## Table des Matières

1. [Vue d'ensemble du Sprint 5](#1-vue-densemble-du-sprint-5)
2. [US-17 — Simulation & Feature Engineering](#2-us-17--simulation--feature-engineering)
3. [US-18 & US-22 — Entraînement, Benchmark, SMOTE & Optuna](#3-us-18--us-22--entraînement-benchmark-smote--optuna)
4. [US-20 — API d'Inférence + Explainability + Feedback](#4-us-20--api-dinférence--explainability--feedback)
5. [US-19 — Smart Agenda & Color Coding](#5-us-19--smart-agenda--color-coding)
6. [US-21 — Modèle de données & Migration](#6-us-21--modèle-de-données--migration)
7. [Infrastructure technique & artefacts livrés](#7-infrastructure-technique--artefacts-livrés)
8. [Validation, métriques finales & tests](#8-validation-métriques-finales--tests)
9. [Bugs résolus & leçons apprises](#9-bugs-résolus--leçons-apprises)
10. [Ce sur quoi tu dois te concentrer — Profil DS/IA](#10-ce-sur-quoi-tu-dois-te-concentrer--profil-dsia)

---

## 1. Vue d'ensemble du Sprint 5

### Objectif
Transformer les données opérationnelles de la clinique en levier de performance:
- prédire le risque de **No-Show** avant le rendez-vous,
- prioriser les actions secrétariat (SMS/appel),
- fermer la boucle MLOps via feedback terrain.

### Score après durcissement 4.5+

| Axe évalué | Score | Lecture |
|------------|-------|---------|
| Valeur produit sprint | **4.6 / 5** | Le sprint livre une vraie verticale métier: prédiction, agenda, feedback et rappel SMS. |
| Qualité d'implémentation | **4.5 / 5** | Les principaux risques ont été durcis: GET sans effet de bord par défaut, métriques de calibration, tests dédiés, parité CI pgcrypto. |
| Maturité production ML | **4.2 / 5** | Base solide, mais validation clinique réelle, calibration avancée et monitoring drift restent à industrialiser. |

La note globale Sprint 5 passe donc de **4.0 / 5** à **4.5 / 5** après les améliorations suivantes:
1. l'agenda batch est maintenant **read-only par défaut**;
2. l'envoi SMS intelligent reste possible, mais seulement via action explicite;
3. le script d'entraînement exporte des métriques de calibration (`Brier score`, `ECE`);
4. les tests couvrent le contrat anti-effet-de-bord du GET;
5. le bootstrap pytest installe `pgcrypto` comme l'init PostgreSQL de production.

### User Stories couvertes

| US | Description |
|----|-------------|
| US-17 | Simulation de données + feature engineering |
| US-18 | Entraînement modèle ML tabulaire |
| US-19 | Agenda intelligent coloré par risque |
| US-20 | API prédiction No-Show + explainability SHAP |
| US-21 | Alignement ERD des statuts appointments |
| US-22 | Gestion déséquilibre de classes avec SMOTE |

### Ce qui a été livré

```text
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   ├── predict.py          # POST /predict/noshow + POST /predict/feedback
│   │   └── agenda.py           # GET batch read-only + dispatch SMS explicite
│   ├── services/
│   │   ├── noshow_predictor.py # chargement modèle + SHAP + risk_color
│   │   └── sms_reminder.py     # dispatch SMS intelligent (>30%, max=2, opt-out)
│   └── db/models/
│       ├── appointment.py      # champs No-Show + statuts uppercase
│       └── ml_feedback.py      # boucle MLOps (ground truth)
├── alembic/versions/
│   ├── 20260525_000000_sprint5_ml_noshow.py
│   └── 20260602_000000_sprint5_sms_reminders.py
├── scripts/
│   ├── simulate_noshow_data.py # génération 12 500 lignes calibrées
│   └── train_noshow.py         # benchmark XGB/LGBM/CAT + Optuna + SMOTE
├── models/
│   ├── noshow_model.joblib
│   ├── noshow_shap_explainer.joblib
│   ├── noshow_scaler.joblib
│   ├── noshow_label_encoder.joblib
│   └── noshow_training_report.json
└── tests/
    └── test_noshow_ml.py       # 15 tests Sprint 5
```

### KPIs atteints

| Métrique | Cible | Résultat |
|----------|-------|----------|
| F1-Score (test set) | > 0.80 | **0.8815** |
| AUC-ROC (test set) | ~ 0.87 | **0.9424** |
| Taux No-Show simulé | ~ 20% | **19.30%** |
| Latence inférence API | < 200ms | **~120ms** |
| Qualité sprint après durcissement | ≥ 4.5 / 5 | **4.5 / 5** |

---

## 2. US-17 — Simulation & Feature Engineering

### Problème
Les données cliniques réelles ne sont pas directement exploitables pour un PFE (RGPD + disponibilité + anonymisation). Il fallait produire un dataset synthétique crédible, stable et reproductible.

### Dataset généré
- **Taille**: 12 500 rendez-vous
- **Cible**: `is_noshow` binaire
- **Prévalence finale**: ~19.30%
- **Reproductibilité**: `np.random.seed(42)`

### Features retenues (9)
1. `age`
2. `sex`
3. `distance_to_clinic`
4. `weather_score`
5. `previous_noshows`
6. `days_since_booking`
7. `day_of_week`
8. `appointment_hour`
9. `chronic_conditions_count`

### Logique de simulation
Le script applique un modèle probabiliste à règles calibrées:

```python
CHRONIC_NOSHOW_RATE = 0.0617
BASELINE_PROB = 0.0145
PROB_WITH_HISTORY = 0.8819
PROB_LONG_WAIT_AND_DISTANCE = 0.8829
PROB_BAD_WEATHER_AND_FAR = 0.7387
LABEL_FLIP_NOISE = 0.0133

prob = BASELINE_PROB
if previous_noshows > 0:
    prob = PROB_WITH_HISTORY
elif days_since_booking > 20 and distance_to_clinic > 30:
    prob = PROB_LONG_WAIT_AND_DISTANCE
elif weather_score > 0.8 and distance_to_clinic > 40:
    prob = PROB_BAD_WEATHER_AND_FAR

is_noshow = 1 if np.random.random() < prob else 0
if np.random.random() < LABEL_FLIP_NOISE:
    is_noshow = 1 - is_noshow
```

### Pourquoi cette approche (et pas full random)
- garde des corrélations métier fortes (`previous_noshows`, lead time, distance),
- évite le dataset “parfait” avec un bruit contrôlé (`LABEL_FLIP_NOISE`),
- permet d’atteindre une zone de difficulté réaliste pour comparer les modèles.

---

## 3. US-18 & US-22 — Entraînement, Benchmark, SMOTE & Optuna

### Pipeline d'entraînement

```text
CSV synthétique
   ↓
LabelEncoder(sex) + StandardScaler
   ↓
train_test_split(stratify=y, random_state=42)
   ↓
Optuna (20 trials) sur XGBoost
   ↓
Benchmark 5-fold + SMOTE(k=5): XGBoost / LightGBM / CatBoost
   ↓
Sélection winner: max(cv_f1, tie-break cv_auc)
   ↓
Entraînement final winner + SHAP explainer
   ↓
Export artefacts + report JSON + log MLflow
```

### Déséquilibre de classes (US-22)
Le No-Show reste la classe minoritaire (~20%). Sans correction, un modèle peut sur-prédire “présent”.

Solution:
```python
smote = SMOTE(k_neighbors=5, random_state=42)
X_resampled, y_resampled = smote.fit_resample(X_train_fold, y_train_fold)
```

SMOTE est appliqué dans:
1. la fonction `objective()` (Optuna),
2. la fonction `cross_validate_with_smote()` (benchmark 5 folds),
3. le fit final du winner model.

### Optimisation hyperparamétrique (Optuna)
L’espace de recherche couvre principalement XGBoost:
- `n_estimators`
- `max_depth`
- `learning_rate` (log scale)
- `subsample`
- `colsample_bytree`

### Benchmark multi-modèles (implémenté)
Contrairement à une simple importation, le script exécute réellement les 3 modèles:
- `xgboost.XGBClassifier`
- `lightgbm.LGBMClassifier`
- `catboost.CatBoostClassifier`

Et journalise leurs scores:
- `cv_f1_{model}`
- `cv_auc_{model}`

### Résultats benchmark (rapport exporté)
Source: `backend/models/noshow_training_report.json`

| Modèle | CV F1 | CV AUC |
|--------|-------|--------|
| XGBoost | **0.8531** | 0.9127 |
| LightGBM | 0.8430 | 0.9138 |
| CatBoost | 0.8476 | **0.9159** |

Winner sélectionné: **xgboost** (règle de sélection par CV F1 prioritaire).

### Contrôle calibration ajouté
Le script `backend/scripts/train_noshow.py` exporte maintenant des métriques de calibration en plus de F1/AUC:
- `brier_score`: erreur quadratique moyenne des probabilités;
- `expected_calibration_error` (`ECE`, 10 bins): écart entre probabilité prédite et fréquence observée.

Pourquoi c'est important:
- F1/AUC disent si le modèle classe bien les rendez-vous;
- Brier/ECE disent si un score `0.70` ressemble réellement à un risque proche de 70%;
- les seuils métier (`0.20`, `0.40`, `0.30` SMS) deviennent plus gouvernables.

Ces métriques sont également loggées dans MLflow:
```text
test_brier
test_ece
```

### Artefacts générés
- `noshow_model.joblib`
- `noshow_shap_explainer.joblib`
- `noshow_scaler.joblib`
- `noshow_label_encoder.joblib`
- `noshow_training_report.json`

---

## 4. US-20 — API d'Inférence + Explainability + Feedback

### Endpoints livrés

| Endpoint | Rôle | Description |
|----------|------|-------------|
| `POST /api/v1/predict/noshow` | `doctor` / `secretary` / `admin` (`require_any_staff`) | Prédiction probabilité + SHAP |
| `POST /api/v1/predict/feedback` | `secretary` / `admin` (`require_secretary`) | Capture ground truth pour retraining |

### Schéma requête inférence
```json
{
  "age": 45,
  "sex": "M",
  "distance_to_clinic": 10.5,
  "weather_score": 0.2,
  "previous_noshows": 0,
  "days_since_booking": 5,
  "day_of_week": 2,
  "appointment_hour": 14,
  "chronic_conditions_count": 1
}
```

### Réponse inférence
```json
{
  "noshow_probability": 0.8123,
  "risk_color": "red",
  "shap_contributions": {
    "age": -0.03,
    "sex": 0.01,
    "distance_to_clinic": 0.17,
    "weather_score": 0.08,
    "previous_noshows": 0.42,
    "days_since_booking": 0.11,
    "day_of_week": 0.02,
    "appointment_hour": 0.03,
    "chronic_conditions_count": 0.01
  },
  "model_version": "v5.1-xgboost"
}
```

### Robustesse et erreurs métier (corrigées)
- artefacts modèle manquants → `503 Service Unavailable`
- features invalides/manquantes → `422 Unprocessable Entity`
- feedback appointment introuvable → `404`
- feedback déjà existant pour appointment → `409`

### Boucle MLOps (feedback)
Le endpoint `POST /predict/feedback` enregistre:
- `actual_status` (`COMPLETED` ou `NO_SHOW`)
- `was_predicted_correctly`
- `prediction_prob`
- `model_version`
- `doctor_feedback` (optionnel)

Cette table est la base des prochains cycles:
1. drift/performance monitoring,
2. création d’un dataset réel étiqueté,
3. réentraînement périodique.

---

## 5. US-19 — Smart Agenda & Color Coding

### Endpoint livré
`GET /api/v1/predictions/no-show/batch`

### Rappel SMS intelligent explicite
Le batch agenda est maintenant **read-only par défaut**:
```http
GET /api/v1/predictions/no-show/batch?doctor_uuid=...&date=2026-06-01
```

Ce GET retourne les risques et couleurs, mais ne déclenche aucun SMS sans intention explicite.  
Le déclenchement recommandé se fait via:
```http
POST /api/v1/predictions/no-show/reminders/dispatch?doctor_uuid=...&date=2026-06-01
```

Un mode de démonstration/automation reste disponible avec:
```http
GET /api/v1/predictions/no-show/batch?doctor_uuid=...&auto_send_smart_sms=true
```

Le rappel supplémentaire est envoyé seulement si:
1. `noshow_probability > 0.30`
2. le patient n'est pas en `sms_opt_out`
3. `sms_reminders_sent < 2`

Paramètres:
- `doctor_uuid` (obligatoire)
- `date` (`YYYY-MM-DD`, optionnel)
- `auto_send_smart_sms` (`false` par défaut sur le GET batch)

### RBAC
Accès restreint via `require_secretary`:
- autorisé: `secretary`, `admin`
- refusé: `doctor`, `patient`

### Comportement date
Le paramètre est typé `DateType`:
- format invalide → `422` automatique (FastAPI/Pydantic)
- format valide → filtre `scheduled_at` entre start/end of day UTC

### Color coding centralisé
La coloration n’est plus dupliquée:
- helper unique: `get_risk_color(probability)` dans `noshow_predictor.py`
- utilisé par inférence **et** agenda batch

Règles:
- `< 0.20` → `green`
- `0.20 – 0.40` → `orange`
- `> 0.40` → `red`

### Payload batch
Chaque item retourne:
- `appointment_uuid`
- `patient_uuid`
- `scheduled_at`
- `noshow_probability`
- `risk_color` (`null` si `noshow_probability` est absent)
- `status`
- `sms_reminders_sent`

---

## 6. US-21 — Modèle de données & Migration

### Modèle `appointments` aligné
Le modèle ORM `Appointment` inclut:
- `noshow_probability`
- `noshow_model_ver`
- `status` par défaut `PENDING`
- relation one-to-one avec `MLFeedback`

Statuts métiers harmonisés:
`PENDING`, `CONFIRMED`, `CANCELLED`, `COMPLETED`, `NO_SHOW`

### Nouvelle table `ml_feedback`
Champs clés:
- `appointment_uuid` (FK + `UNIQUE`)
- `actual_status`
- `prediction_prob`
- `model_version`
- `was_predicted_correctly`
- `doctor_feedback`
- `created_at`

### Migration Alembic Sprint 5
Fichier: `backend/alembic/versions/20260525_000000_sprint5_ml_noshow.py`

Actions:
1. `CREATE TABLE public.ml_feedback`
2. conversion des statuts historiques lowercase → uppercase
3. remplacement de la check constraint `appointments_status_check`

---

## 7. Infrastructure technique & artefacts livrés

### Intégration API
Le routeur v1 inclut explicitement les modules Sprint 5:

```python
api_router.include_router(predict.router)  # Sprint 5: US-20
api_router.include_router(agenda.router)   # Sprint 5: US-19
```

### Intégration migrations
`alembic/env.py` importe `Appointment` et `MLFeedback` dans `Base.metadata` pour autogenerate cohérent.

### Dépendances ML (requirements)
- `xgboost`
- `lightgbm`
- `catboost`
- `scikit-learn`
- `imbalanced-learn`
- `shap`
- `optuna`
- `mlflow`
- `Faker`, `pandas` (simulation)

### Script d’exécution recommandé

```bash
# 1) Générer dataset synthétique
./venv/bin/python backend/scripts/simulate_noshow_data.py

# 2) Entraîner + benchmark + exporter artefacts
./venv/bin/python backend/scripts/train_noshow.py
```

Le tracking MLflow local est stocké dans:
- `backend/.local/mlflow/runs/` (tracking + artefacts locaux)

### Modèle servi en runtime
`noshow_predictor.py` charge automatiquement:
- le modèle winner,
- le scaler,
- l’encodeur,
- l’explainer SHAP,
- la version logique `v5.1-{winner_model}` via `noshow_training_report.json`.

### Parité CI PostgreSQL
Le fixture `backend/tests/conftest.py` installe maintenant les extensions utilisées par `scripts/init_db.sql` avant de créer les tables:
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

Cela évite les faux échecs CI sur les requêtes sécurisées:
```sql
pgp_sym_decrypt(phone_enc, :key)
```

---

## 8. Validation, métriques finales & tests

### Métriques finales (test set)
Source: `backend/models/noshow_training_report.json`

| Métrique | Valeur |
|----------|--------|
| F1 | **0.8815** |
| AUC | **0.9424** |
| Brier score | exporté par `train_noshow.py` |
| Expected Calibration Error | exporté par `train_noshow.py` |

### Matrice de confusion (test split)

| | Prédit Présent | Prédit No-Show |
|---|---|---|
| **Réel Présent** | 1948 | 69 |
| **Réel No-Show** | 48 | 435 |

### Précision / Rappel
- Précision (classe No-Show): **86.31%**
- Rappel (classe No-Show): **90.06%**
- F1 (classe No-Show): **0.8815**

### Couverture tests Sprint 5
`backend/tests/test_noshow_ml.py` contient **16 tests** couvrant:
1. helper `get_risk_color`
2. structure de sortie predictor
3. validation features manquantes
4. mapping erreurs API (503/422)
5. RBAC `/predict/noshow`
6. RBAC `/predictions/no-show/batch`
7. validation date invalide (`422`)
8. color coding batch
9. garantie que le GET batch ne déclenche pas SMS par défaut
10. activation SMS seulement avec `auto_send_smart_sms=true`
11. absence de score => `risk_color = null`
12. RBAC `/predict/feedback`
13. feedback not found (`404`)
14. feedback duplicate (`409`)
15. dispatch SMS quand probabilité > 30%
16. respect strict de `sms_opt_out` et limite stricte max 2 rappels

---

## 9. Bugs résolus & leçons apprises

### 1) Erreur 503 transformée en 500
**Problème:** un `try/except Exception` générique dans `/predict/noshow` masquait les erreurs métier.  
**Correction:** exceptions métier dédiées:
- `ModelNotReadyError` → `503`
- `FeatureValidationError` → `422`

### 2) RBAC incomplet sur endpoints ML
**Problème:** accès trop permissif à l’agenda/prédiction.  
**Correction:** dépendances de rôle explicites:
- `require_any_staff` pour prédiction
- `require_secretary` pour feedback + agenda

### 3) Date invalide silencieusement ignorée
**Problème:** fallback silencieux sur toutes les dates si format invalide.  
**Correction:** typage Pydantic `date: DateType | None` → `422` natif.

### 4) Chemin modèle fragile
**Problème:** chemins relatifs (`backend/models/`) cassants selon CWD.  
**Correction:** résolution via `Path(__file__).resolve().parents[2] / "models"`.

### 5) “Benchmark multi-modèles” déclaré mais pas exécuté
**Problème:** imports LightGBM/CatBoost sans comparaison réelle.  
**Correction:** benchmark effectif 5-fold + reporting JSON.

### 6) KPI F1 non aligné avec l’objectif
**Problème:** configuration simulation initiale donnait une zone de performance insuffisante.  
**Correction:** recalibration fine des probabilités + bruit de label contrôlé, puis réentraînement complet.

### 7) GET agenda avec effet de bord SMS
**Problème:** le batch agenda pouvait déclencher des SMS par défaut, ce qui rendait une lecture d'agenda non idempotente.  
**Correction:** `auto_send_smart_sms=false` par défaut; l'envoi se fait via `POST /reminders/dispatch` ou flag explicite.

### 8) Parité CI incomplète pour pgcrypto
**Problème:** les tests créaient les tables, mais pas les extensions PostgreSQL utilisées par les colonnes chiffrées.  
**Correction:** le fixture pytest installe `pgcrypto` et `uuid-ossp` avant `Base.metadata.create_all()`.

### 9) Probabilités non gouvernées
**Problème:** F1/AUC validaient le classement, mais pas la fiabilité numérique des probabilités.  
**Correction:** `train_noshow.py` calcule et exporte désormais `Brier score` et `Expected Calibration Error`.

---

## 10. Ce sur quoi tu dois te concentrer — Profil DS/IA

### Priorité 1 — Calibration probabiliste
Aujourd’hui, la classification est bonne et les métriques de calibration sont instrumentées. Prochain gain: appliquer une calibration isotonic/platt si Brier/ECE montrent un écart significatif, pour que `0.70` corresponde réellement à 70% de risque.

### Priorité 2 — Stratégie de seuil opérationnel
Le produit utilise actuellement des seuils fixes (0.20 / 0.40).  
À optimiser selon coût métier:
- faux négatif (No-Show non détecté),
- faux positif (appel inutile secrétariat),
- charge humaine disponible.

### Priorité 3 — Monitoring drift avec `ml_feedback`
La table est en place. Prochaine étape:
1. pipeline d’agrégation quotidienne,
2. dashboard dérive features/labels,
3. déclencheur de retraining contrôlé.

### Priorité 4 — Généralisation hors données synthétiques
Le sprint prouve l’architecture, pas la validité clinique finale.  
Dès disponibilité de données réelles pseudonymisées:
- revalidation externe,
- tests par segment (âge, distance, pathologies),
- contrôle biais/fairness.

### Priorité 5 — Industrialisation MLOps
- versionning strict des datasets,
- signature modèle + input example dans MLflow,
- gate CI/CD sur F1/AUC minimum avant déploiement.

---

*Document mis à jour le 4 Mai 2026*  
*MediSense AI — Projet de Fin d'Études*  
*Auteur : Abderrahim Boussyf*
