# Sprint 7 — IoT Pipeline & LSTM Anomalie : Détail Complet
**22 Juin – 05 Juillet 2026 | Statut : ⏳ EN COURS**

> Ce document explique **ce qui a été conçu**, **pourquoi chaque décision d'architecture a été prise**, et **ce sur quoi tu dois te concentrer** en tant que profil Data Science & IA pour comprendre, implémenter et valider le pipeline IoT temps-réel et le modèle LSTM de détection d'anomalies biométriques.

---

## Table des Matières

1. [Vue d'ensemble du Sprint 7](#1-vue-densemble-du-sprint-7)
2. [Fondation livrée en avance (Sprint 4)](#2-fondation-livrée-en-avance-sprint-4)
3. [US-25 — Ingestion Kafka IoT 10 msg/s](#3-us-25--ingestion-kafka-iot-10-msgs)
4. [US-26 — TimescaleDB hypertable](#4-us-26--timescaledb-hypertable)
5. [US-27 — LSTM Bidirectionnel PyTorch (AUC-ROC > 0.85)](#5-us-27--lstm-bidirectionnel-pytorch-auc-roc--085)
6. [US-28 — Détection sur 2 fenêtres glissantes](#6-us-28--détection-sur-2-fenêtres-glissantes)
7. [US-29 — Push notification au réveil (accéléromètre)](#7-us-29--push-notification-au-réveil-accéléromètre)
8. [Infrastructure technique & artefacts prévus](#8-infrastructure-technique--artefacts-prévus)
9. [Métriques cibles & validation](#9-métriques-cibles--validation)
10. [Décisions d'architecture & leçons de conception](#10-décisions-darchitecture--leçons-de-conception)
11. [Ce sur quoi te concentrer — Profil DS/IA](#11-ce-sur-quoi-te-concentrer--profil-dsia)

---

## 1. Vue d'ensemble du Sprint 7

### Objectif
Connecter les capteurs biométriques portables (Samsung Watch) à la plateforme MediSense AI :
- ingérer en continu les métriques vitales via Apache Kafka (10 msg/s),
- persister dans TimescaleDB avec compression automatique,
- détecter les anomalies temporelles via un LSTM Bidirectionnel PyTorch (AUC-ROC > 0.85),
- alerter le patient via push notification et enrichir le contexte RAG en temps réel.

### Résultat cible

| Axe évalué | Score cible | Lecture |
|------------|:-----------:|---------|
| Valeur produit sprint | **4.5 / 5** | Le patient voit ses données vitales et reçoit une alerte avant une urgence. |
| Qualité ML | **4.5 / 5** | LSTM BiDir + attention, AUC-ROC > 0.85 sur données synthétiques Samsung Health. |
| Maturité production IoT | **4.0 / 5** | Pipeline Kafka → TimescaleDB → LSTM validé en débit continu 10 msg/s. |
| Résilience | **3.5 / 5** | Mode dégradé Kafka reporté en Sprint 8 (US-30). |

### User Stories couvertes

| US | Description | Story Points | Priorité | Statut |
|----|-------------|:------------:|:--------:|:------:|
| US-25 | Ingestion Kafka biométriques : 10 msg/s en débit continu | 8 | Must | ⏳ |
| US-26 | TimescaleDB hypertable : partitionnement par jour, compression auto | 5 | Should | ⏳ |
| US-27 | LSTM Bidirectionnel PyTorch : AUC-ROC > 0.85 sur données synthétiques | 13 | Must | ⏳ |
| US-28 | Détection sur 2 fenêtres glissantes : 5 min (critique) + 60 min (tendance) | 8 | Should | ⏳ |
| US-29 | Push notification au réveil (détection accéléromètre) | 5 | Should | ⏳ |
| **Total** | | **39 pts** | | |

### Ce qui doit être livré

```text
backend/
├── app/
│   ├── api/v1/endpoints/
│   │   └── ingest.py                    # POST /iot/ingest (internal, Kafka consumer)
│   ├── services/
│   │   ├── kafka_consumer.py            # US-25 aiokafka async consumer
│   │   └── anomaly_detector.py          # US-28 sliding window Redis sorted sets
│   └── db/models/                       # déjà livré — voir section 2
│       ├── biometric_reading.py         # ✅ Sprint 4
│       ├── biometric_anomaly.py         # ✅ Sprint 4
│       └── iot_device.py                # ✅ Sprint 4
├── scripts/
│   └── train_lstm_anomaly.py            # US-27 training script + MLflow tracking
├── alembic/versions/
│   └── 20260622_000000_sprint7_timescaledb.py  # US-26 create_hypertable migration
├── tests/
│   ├── test_iot.py                      # ✅ 9 tests existants (Sprint 4)
│   ├── test_kafka_consumer.py           # US-25 consumer tests
│   └── test_anomaly_detector.py        # US-27/28 inference + window tests
docs/
└── SPRINT_7_DETAILS.md                  # ce fichier
docker-compose.yml                       # +kafka +timescaledb services
requirements.txt                         # +aiokafka +torch +timescaledb
```

---

## 2. Fondation livrée en avance (Sprint 4)

Le Sprint 7 bénéficie d'une infrastructure de données pré-construite lors du Sprint 4 pour débloquer les US-13 (contexte IoT dans le chat) et US-41 (résumé DPA).

### Modèles de données

#### `app/db/models/biometric_reading.py`
Stocke les lectures brutes des capteurs (HR, SpO2, HRV).

```python
class BiometricReading(Base):
    __tablename__ = "biometric_reading"
    id: Mapped[uuid.UUID]          # PK
    patient_uuid: Mapped[uuid.UUID]  # FK → patients.patient_uuid
    ts: Mapped[datetime]           # horodatage avec timezone (index)
    hr: Mapped[int]                # fréquence cardiaque (bpm)
    spo2: Mapped[int]              # saturation O2 (%)
    hrv: Mapped[int]               # variabilité cardiaque (ms)
```

#### `app/db/models/biometric_anomaly.py`
Stocke les anomalies pré-classifiées par le LSTM.

Décisions de conception clés (documentées dans le fichier source) :
- **`metric_type` VARCHAR(30)** au lieu d'ENUM → de nouveaux types de capteurs peuvent être ajoutés sans migration de schéma.
- **Sévérité pré-classifiée à l'ingestion** (`mild | moderate | critical`) → évite de recalculer à chaque requête.
- **Pas de FK SQLAlchemy sur `patient_id`** → TimescaleDB peut vivre sur un nœud DB séparé en production ; l'intégrité référentielle est assurée par la couche applicative.
- **Hypertable TimescaleDB** (Sprint 7) : `SELECT create_hypertable('biometric_anomalies', 'detected_at')` — migration transparente car TimescaleDB est 100% compatible PostgreSQL.

#### `app/db/models/iot_device.py`
État du dispositif paired : `patient_uuid`, `last_sync`, `battery_pct`, `model`.

### Endpoints existants (`app/api/v1/endpoints/iot.py`)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/v1/iot/vitals?range=7d` | `require_patient` | Lectures biométriques filtrées par plage temporelle (`7d`, `24h`) |
| `GET /api/v1/iot/devices` | `require_patient` | Statut du dispositif paired (batterie, dernière synchro) |

Le paramètre `range` est validé par regex `^(\d+)([dh])$` — 422 si format invalide.

### RAG — Contexte IoT (`app/rag/iot_context.py`)

Ce module est inséré en **Étape 0** (avant la détection de langue) dans `pipeline.run()` et `pipeline.run_stream()`.

**Stratégie de requête :** 5 dernières anomalies sur 30 jours, ordonnées newest-first.
- 5 anomalies : assez pour détecter une tendance (ex. 3 chutes SpO2 consécutives) sans noyer le contexte LLM.
- 30 jours : fenêtre cliniquement pertinente pour les conditions chroniques.

**Dégradation gracieuse :** si TimescaleDB/PostgreSQL est injoignable, `IoTContext` vide est retourné — le chat n'est jamais bloqué, même en urgence.

**Mode mock (`MOCK_IOT=true`)** : retourne des anomalies réalistes (SpO2=92%, HR=105bpm) sans infrastructure IoT — permet de développer Sprint 4 sans Sprint 7.

```python
@dataclass
class IoTContext:
    anomalies: list[dict]   # sérialisés via BiometricAnomaly.to_context_dict()
    has_critical: bool      # déclenche l'override de sécurité pré-LLM
    summary_text: str       # injecté directement dans le prompt LLM
```

### Tests IoT existants (`tests/test_iot.py`)
9 tests couvrant : happy path vitaux, filtrage par plage, rejet auth 403, format invalide 422, statut dispositif, 404 dispositif absent.

---

## 3. US-25 — Ingestion Kafka IoT (10 msg/s)

### Problème
Les capteurs Samsung Watch émettent des données biométriques en continu. Un appel HTTP direct backend→capteur est impraticable (mobile derrière NAT, perte de données si le backend est indisponible, pas de replay en cas d'erreur).

### Solution : Apache Kafka comme source-of-truth du streaming

```
Samsung Watch (BLE)
    ↓
Smartphone patient (app Flutter)
    ↓  HTTP POST /iot/ingest  (JWT patient)
FastAPI backend
    ↓  producer.send("iot-vitals", msg)
Apache Kafka  ──── topic: iot-vitals (1 partition, retention 7j)
    ↓  consumer group: medisense-iot
kafka_consumer.py (aiokafka)
    ↓  INSERT INTO biometric_reading
PostgreSQL / TimescaleDB
```

**Pourquoi Kafka et non MQTT direct ?**
- **Replay** : Kafka conserve les messages 7 jours — le LSTM peut rejouer l'historique pour (ré)entraînement.
- **Découplage** : le consumer LSTM peut être redéployé sans perdre de données.
- **Back-pressure** : si le backend est lent, Kafka tampon — pas de perte à la source.

### Code à créer

**`app/services/kafka_consumer.py`**
```python
# Consommateur aiokafka lancé dans le lifespan FastAPI
# Group ID: "medisense-iot"  Topic: settings.KAFKA_TOPIC_IOT
# Commit offsets manuels après INSERT confirmé
```

**`app/api/v1/endpoints/ingest.py`**
```python
# POST /api/v1/iot/ingest — auth require_patient
# Body: { ts, hr, spo2, hrv }  → INSERT biometric_reading + forward to Kafka
```

### Variables de configuration à ajouter (`app/core/config.py`)

```python
KAFKA_BROKERS: list[str] = ["kafka:9092"]
KAFKA_TOPIC_IOT: str = "iot-vitals"
KAFKA_CONSUMER_GROUP: str = "medisense-iot"
KAFKA_BUFFER_DIR: str = "/tmp/kafka-buffer"  # US-30 mode dégradé
```

---

## 4. US-26 — TimescaleDB hypertable

### Problème
Les lectures biométriques croissent rapidement (1 lecture/30s × N patients). Les requêtes `WHERE ts >= cutoff ORDER BY ts` sur une table régulière PostgreSQL dégradent en O(n) sans partitionnement temporel.

### Solution : Extension TimescaleDB sur PostgreSQL 16

**Avantage clé :** TimescaleDB est une extension PostgreSQL — toutes les requêtes SQL existantes fonctionnent sans modification. Il n'y a pas de migration applicative, uniquement une migration Alembic.

### Migration Alembic (`alembic/versions/20260622_000000_sprint7_timescaledb.py`)

```sql
-- Convertir biometric_reading en hypertable
SELECT create_hypertable('biometric_reading', 'ts', if_not_exists => TRUE);

-- Compression automatique des chunks > 7 jours
ALTER TABLE biometric_reading SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'ts DESC',
    timescaledb.compress_segmentby = 'patient_uuid'
);
SELECT add_compression_policy('biometric_reading', INTERVAL '7 days');

-- Même traitement pour biometric_anomalies
SELECT create_hypertable('biometric_anomalies', 'detected_at', if_not_exists => TRUE);
ALTER TABLE biometric_anomalies SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'patient_id'
);
SELECT add_compression_policy('biometric_anomalies', INTERVAL '7 days');
```

**Pourquoi `compress_segmentby = 'patient_uuid'` ?**
La requête dominante est `WHERE patient_uuid = $1 AND ts >= $2`. TimescaleDB crée des mini-colonnes par patient → compression 10x sur les colonnes HR/SpO2/HRV à faible cardinalité.

### Service docker-compose à ajouter

```yaml
timescaledb:
  image: timescale/timescaledb-ha:pg16-latest
  environment:
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - timescaledb_data:/var/lib/postgresql/data
  ports:
    - "5433:5432"   # port distinct pour ne pas conflictuels avec postgres:16
```

> Note : en option, on peut activer l'extension TimescaleDB directement sur le service `postgres:16` existant via `shared_preload_libraries = 'timescaledb'` — évite un 7e service.

---

## 5. US-27 — LSTM Bidirectionnel PyTorch (AUC-ROC > 0.85)

### Problème
Les anomalies biométriques ne se détectent pas sur un point isolé (une seule valeur SpO2=92% peut être un artefact de capteur). Il faut analyser un **motif temporel** : 3 chutes consécutives de SpO2 sur 10 min sont cliniquement significatives.

### Architecture LSTM

```
Input: [T-N, ..., T]  →  N=120 points × 4 features (HR, SpO2, HRV, temp)
       normalisé par baseline patient (z-score individuel, pas global)
    ↓
BiLSTM layer 1 : hidden=128, dropout=0.3  (forward + backward)
    ↓
BiLSTM layer 2 : hidden=64, dropout=0.2
    ↓
Attention (additive, Bahdanau) : poids temporels appris
    ↓
Fully connected : 128 → 1
    ↓
Sigmoid → anomaly_score ∈ [0.0, 1.0]
    ↓
Classification :
  score < 0.4  → normal
  score ∈ [0.4, 0.7] → mild
  score ∈ [0.7, 0.85] → moderate
  score > 0.85 → critical
```

**Pourquoi BiLSTM et non Transformer ?**
- Fenêtres de 120 points max → la complexité quadratique du Transformer n'est pas justifiée.
- BiLSTM capture les dépendances à long terme dans les deux directions (montée progressive + chute soudaine).
- Empreinte mémoire 4x inférieure à un Transformer de complexité équivalente pour cette taille d'entrée.

**Pourquoi z-score par patient (baseline individuel) ?**
Un HR=90bpm est normal pour un athlète (baseline 85bpm) mais anormal pour un patient sédentaire (baseline 65bpm). La normalisation globale masquerait ces différences inter-patients.

### Script d'entraînement (`scripts/train_lstm_anomaly.py`)

Suit le même pattern que `scripts/train_noshow.py` (Sprint 5/6) :

```python
# 1. Génération données synthétiques (format Samsung Health)
# 2. Feature engineering : fenêtres glissantes 120pts, normalisation par patient
# 3. Entraînement PyTorch + validation croisée 5-fold
# 4. Quality gate : AUC-ROC > 0.85, F1 > 0.78
# 5. MLflow tracking : paramètres, métriques, artefacts (ROC curve, matrice confusion)
# 6. Enregistrement Registry si quality gate passe :
#    mlflow.register_model(..., "lstm-anomaly")
#    client.set_registered_model_alias("lstm-anomaly", "champion", version)
```

**Intégration MLflow Registry** : réutilise exactement le pattern Sprint 6 (US-33). L'alias `lstm-anomaly@champion` est utilisé par le service d'inférence.

### Endpoint d'inférence (`app/api/v1/endpoints/anomalies.py`)

```python
# POST /api/v1/internal/anomaly — interne, appelé par kafka_consumer
# Body: { patient_id, window_120pts }
# → LSTM inference → INSERT biometric_anomalies → broadcast WebSocket si critical
```

---

## 6. US-28 — Détection sur 2 fenêtres glissantes

### Problème
Une seule fenêtre ne suffit pas :
- Fenêtre **5 min** : détecte les urgences immédiates (SpO2 chute brutal → appel d'urgence).
- Fenêtre **60 min** : détecte les tendances chroniques (HR légèrement élevé toute la matinée → inclure dans le rapport DPA).

### Solution : Redis Sorted Sets pour les fenêtres glissantes

```python
# app/services/anomaly_detector.py
# Redis ZSET key: f"vitals:{patient_id}"
# Score = timestamp UNIX → ZRANGEBYSCORE(now-300, now) pour 5min
#                        → ZRANGEBYSCORE(now-3600, now) pour 60min
```

**Pourquoi Redis et non PostgreSQL ?**
Les fenêtres glissantes nécessitent des lectures très fréquentes (toutes les 30s par patient actif). PostgreSQL avec index temporel est adapté au stockage historique, mais Redis Sorted Sets offrent des lectures O(log n) avec TTL automatique — pas de purge manuelle.

### Logique de dispatch

| Fenêtre | Seuil sévérité | Action |
|---------|:-------------:|--------|
| 5 min | `critical` | Push FCM immédiat + alert WebSocket médecin |
| 5 min | `moderate` | Enregistrement DPA + SMS rappel médecin |
| 60 min | `mild` × 3+ | Rapport de tendance ajouté au résumé DPA |
| 60 min | `moderate` | Escalade vers `critical` si persistant 2h |

---

## 7. US-29 — Push notification au réveil (accéléromètre)

### Problème
Notifier un patient endormi d'une anomalie critique (SpO2 nocturne) via une simple push notification risque d'être ignoré. L'accéléromètre détecte le réveil → notification déclenchée au bon moment.

### Solution

**Côté mobile (Flutter — Sprint 9/10 déjà câblé) :**
- `sensors_plus` package → stream accéléromètre
- Détection réveil : `|acc_z| > 0.3 g` pendant > 2s après 6h d'immobilité
- `POST /api/v1/iot/wake-event { patient_id, ts }` → backend

**Côté backend :**
- `GET /api/v1/iot/pending-alerts?patient_id=...` → retourne anomalies critiques non-acquittées
- FCM `data` message (non `notification`) : affiché uniquement quand l'app est au premier plan ou au réveil de l'écran

**Réutilisation pile FCM :** le token FCM est déjà stocké dans la table `users.fcm_token` (Sprint 9/10) — aucun nouveau modèle de données nécessaire.

---

## 8. Infrastructure technique & artefacts prévus

### Services docker-compose à ajouter

```yaml
kafka:
  image: confluentinc/cp-kafka:7.6.1
  environment:
    KAFKA_KRAFT_MODE: "true"
    KAFKA_PROCESS_ROLES: "broker,controller"
    KAFKA_NODE_ID: 1
    KAFKA_LISTENERS: "PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093"
    KAFKA_ADVERTISED_LISTENERS: "PLAINTEXT://kafka:9092"
    KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka:9093"
    KAFKA_LOG_DIRS: "/tmp/kraft-combined-logs"
    CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
  ports:
    - "9092:9092"
  healthcheck:
    test: ["CMD", "kafka-topics", "--bootstrap-server", "kafka:9092", "--list"]
    interval: 30s
    timeout: 10s
    retries: 5
```

### Dépendances Python à ajouter (`requirements.txt`)

```
aiokafka>=0.10.0      # consumer Kafka async
torch>=2.2.0          # LSTM BiDir
numpy>=1.26.0         # feature engineering
```

### Variables `.env.example` à ajouter

```bash
KAFKA_BROKERS=kafka:9092
KAFKA_TOPIC_IOT=iot-vitals
KAFKA_CONSUMER_GROUP=medisense-iot
KAFKA_BUFFER_DIR=/tmp/kafka-buffer
MOCK_IOT=false
```

### Artefacts MLflow Sprint 7

| Artefact | Description |
|----------|-------------|
| `lstm_anomaly_roc_curve.png` | Courbe AUC-ROC (validation hold-out 20%) |
| `lstm_anomaly_confusion_matrix.png` | Matrice de confusion 4 classes (normal/mild/moderate/critical) |
| `lstm_anomaly_calibration.csv` | Scores de calibration Brier + ECE par classe |
| `model.pth` | Poids PyTorch enregistrés + architecture JSON |

---

## 9. Métriques cibles & validation

| Métrique | Cible | Méthode de mesure |
|----------|:-----:|-------------------|
| LSTM AUC-ROC | **> 0.85** | Données synthétiques Samsung Health format (hold-out 20%) |
| Kafka throughput soutenu | **10 msg/s pendant 60s** | `kafka-producer-perf-test` |
| Latence détection anomalie critique | **< 500ms** | Kafka ingestion → `biometric_anomalies` INSERT |
| Compression TimescaleDB | **> 5x** | `SELECT pg_size_pretty(after_compression_total_bytes)` |
| Dégradation gracieuse chat | **0 timeout** | Test : couper DB pendant chat → chat continue |
| Couverture tests | **≥ 80%** | `make cov` (gate CI maintenu) |

---

## 10. Décisions d'architecture & leçons de conception

### D1 — Pas de FK TimescaleDB → PostgreSQL principal
**Raison :** TimescaleDB peut migrer sur un nœud distinct (volumétrie IoT distincte des données médicales). Référentiel d'intégrité à la couche applicative via `patient_id` UUID validé au JWT decode.

### D2 — `metric_type` VARCHAR(30) et non ENUM
**Raison :** Nouveaux capteurs (glycémie, température, ECG) = zéro migration. ENUM PostgreSQL nécessite un `ALTER TYPE ADD VALUE` non transactionnel en migration Alembic.

### D3 — Sévérité pré-classifiée à l'ingestion (pas à la requête)
**Raison :** `app/rag/iot_context.py` filtre `has_critical` à chaque message de chat. Calculer la sévérité à la requête multiplierait les inférences LSTM par le volume de chat.

### D4 — Normalisation z-score par patient et non globale
**Raison :** Baselines HR/SpO2 sont hautement individuelles (âge, condition physique, traitement). Un seuil global de HR > 100bpm fausserait le modèle pour des profils extrêmes.

### D5 — `MOCK_IOT=true` pour le développement Sprint 4-6
**Raison :** L'infrastructure Kafka/TimescaleDB n'existe pas encore. Le mock retourne des anomalies réalistes (SpO2=92%, HR=105bpm) pour tester les US-13 et US-41 sans dépendance matérielle.

---

## 11. Ce sur quoi te concentrer — Profil DS/IA

### Pour comprendre le sprint rapidement

1. **Lire `app/rag/iot_context.py`** — 188 lignes, très bien commentées. C'est le point d'entrée IoT dans le pipeline IA déjà en production.
2. **Lire `app/db/models/biometric_anomaly.py`** — les commentaires expliquent pourquoi pas de FK, VARCHAR vs ENUM, et la stratégie TimescaleDB.
3. **Lire `scripts/train_noshow.py`** — c'est le template exact à suivre pour `train_lstm_anomaly.py` (MLflow tracking + quality gate).

### Points d'attention DS/IA

- **Données synthétiques Sprint 7** : générer des séries temporelles réalistes (Samsung Health format : HR toutes les 5 min, SpO2 toutes les 15 min) avec injection d'anomalies contrôlées (chutes SpO2, pics HR, arythmies simulées).
- **Validation LSTM** : ne pas utiliser de validation temporelle naïve (train sur jan-mars, test sur avril). Utiliser une validation "leave-one-patient-out" pour éviter la fuite de baseline individuelle entre split train/test.
- **Calibration** : comme pour le No-Show (Sprint 5), produire les courbes de calibration Brier + ECE. Un LSTM bien classé mais mal calibré (score 0.9 mais précision réelle 0.6) est inutile pour le médecin.
- **Attention mechanism** : visualiser les poids d'attention pour vérifier que le modèle regarde les bons instants (chute SpO2 à T-5min doit avoir un poids plus élevé que les valeurs normales à T-60min).
