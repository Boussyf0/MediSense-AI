# MediSense AI — Guide de démo soutenance (16/09/2026)

**Durée totale : 30 minutes**  
**Public :** Jury PFE + encadrants  
**Profil mis en avant :** Data Science / IA — RAG multilingue, ML prédictif, IoT/anomaly detection, MLOps

---

## Checklist pré-démo (J-1 et le matin même)

```bash
# 1. Lancer les services Docker
docker-compose up -d
sleep 20

# 2. Vérifier que tout est up
docker-compose ps
# postgres ✅  redis ✅  qdrant ✅  backend ✅  prometheus ✅  grafana ✅

# 3. Smoke test complet
python scripts/smoke_test.py
# Attendu : 8/8 passed — ready for demo!

# 4. Seed des données de démo
cd backend && python scripts/seed_admin.py

# 5. Vérifier le modèle no-show est chargé
curl -s http://localhost:8000/api/v1/health | python -m json.tool
# "noshow_model": "loaded", "qdrant": "ok", "redis": "ok"

# 6. Grafana dashboard
open http://localhost:3001  # admin / admin
```

**Comptes de démo :**
| Rôle | Email | Mot de passe |
|---|---|---|
| Admin | admin@medisense.ma | Admin1234! |
| Médecin | doctor@medisense.ma | Doctor1234! |
| Patient | patient@medisense.ma | Patient1234! |

---

## Scénario 1 — RAG Multilingue (8 min)

**Message clé pour le jury :** "Notre pipeline RAG indexe 96 303 chunks médicaux (ICD-10, BDPM, ANSM, HAS, protocoles marocains) et répond en Français, Arabe et Darija."

### Étapes

**1.1 Connexion médecin**
```
→ Ouvrir http://localhost:3000
→ Login : doctor@medisense.ma / Doctor1234!
→ Aller dans "Chat IA" (sidebar gauche)
```

**1.2 Question en Français (30s)**
```
Taper : "Quels sont les critères diagnostiques du diabète de type 2 selon la HAS ?"
→ Attendre la réponse streaming (SSE)
→ Montrer les sources affichées (HAS 2023, ICD-10 E11)
→ Pointer : "Chaque réponse cite ses sources — traçabilité médicale"
```

**1.3 Question en Darija (30s)**
```
Taper : "شنو هي أعراض ضغط الدم العالي ؟"
→ La réponse revient en Arabe + protocoles marocains
→ Pointer : "Détection automatique de langue — Darija reconnue via heuristique stopwords"
```

**1.4 Question clinique complexe (1min)**
```
Taper : "Un patient de 65 ans, HTA, vient pour toux sèche depuis 3 semaines. Quelle démarche ?"
→ Montrer le re-ranking (cross-encoder mmarco) dans les sources
→ Pointer : "Pipeline hybride dense + BM25 + RRF — précision clinique"
```

**Points à souligner :**
- Latence < 2s premier token (Groq) ou streaming local (Ollama)
- Hybrid search : vecteurs `multilingual-e5-base` + BM25 dans Qdrant
- Re-ranking cross-encoder pour précision maximale
- Contexte IoT injecté automatiquement si patient a des vitaux récents

---

## Scénario 2 — No-Show Predictor + CRM (8 min)

**Message clé :** "XGBoost F1=0.88 AUC=0.94 entraîné sur 10 000 rendez-vous synthétiques HIPAA-compliant. Explication SHAP par patient."

### Étapes

**2.1 Agenda CRM**
```
→ Aller dans "CRM" (sidebar)
→ Montrer le tableau des tâches avec colonnes : Patient, Risque, Statut, Action
→ Filtrer par risque HIGH : 3-4 patients avec badge rouge
```

**2.2 Détail d'un patient à risque élevé (1min)**
```
→ Cliquer sur un patient HIGH risk
→ Afficher le score : ex. 0.87 (87% probabilité de no-show)
→ Montrer les facteurs SHAP :
   - "Historique no-show : +0.23"
   - "Distance domicile > 15km : +0.18"
   - "SMS non confirmé : +0.15"
→ Pointer : "Explicabilité SHAP — le médecin comprend POURQUOI le modèle prédit"
```

**2.3 Envoi de rappel SMS (30s)**
```
→ Cliquer "Envoyer SMS de rappel"
→ POST /api/v1/predictions/no-show/reminders/dispatch
→ Toast : "SMS envoyé à +212..."
→ Pointer : "Seuil configurable : SMS si score > 30%, max 2 rappels par patient"
```

**2.4 Sync Salesforce CRM (30s)**
```
→ Montrer le badge "Salesforce SYNC ✅" sur la tâche
→ Expliquer le circuit breaker : "Si Salesforce est down, 3 retries + état local"
```

**2.5 MLflow Model Registry (1min)**
```
→ Ouvrir http://localhost:5000 (MLflow UI) — si disponible
→ Ou montrer backend/models/noshow_training_report.json
→ "Registered model alias 'champion' — auto-promoted si F1≥0.80 et AUC≥0.87"
```

**Points à souligner :**
- SMOTE pour équilibrage classes (no-show ~25%)
- Optuna HPO (20 trials) + benchmark XGBoost vs LightGBM vs CatBoost
- Calibration Brier score ≤ 0.12
- Seuil SMS configurable via `SMS_REMINDER_THRESHOLD` (Settings)

---

## Scénario 3 — IoT Anomaly Detection (8 min)

**Message clé :** "BiLSTM bidirectionnel avec attention de Bahdanau — AUC-ROC > 0.85 sur données Samsung Watch simulées. Deux fenêtres glissantes : 5min (critique) et 60min (tendance)."

### Étapes

**3.1 Tableau de bord IoT**
```
→ Aller dans "IoT" (sidebar)
→ Montrer GET /api/v1/iot/vitals — dernières mesures en temps réel
→ Colonnes : Appareil, FC, SpO2, HRV, Température, Statut
```

**3.2 Simulation d'une anomalie (2min)**
```bash
# Dans un terminal séparé — simuler une anomalie critique
curl -X POST http://localhost:8000/api/v1/anomalies/detect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_uuid": "DEMO-PATIENT-UUID",
    "window_minutes": 5,
    "vitals": {
      "hr": [45, 43, 41, 38, 35],
      "spo2": [94, 92, 90, 88, 86],
      "hrv": [12, 10, 8, 7, 6],
      "temperature": [38.1, 38.3, 38.5, 38.7, 38.9]
    }
  }'
# Réponse attendue : {"anomaly_score": 0.94, "severity": "CRITICAL", "alert_sent": true}
```

**3.3 Alerte temps réel (30s)**
```
→ Montrer la notification dans l'interface
→ "L'alerte WebSocket arrive en < 500ms"
→ Le DPA reçoit un résumé automatique via /doctor/dpa-summary
```

**3.4 Grafana Dashboard (1min)**
```
→ Ouvrir http://localhost:3001/d/medisense-overview
→ Montrer les panneaux :
   - "HTTP Requests/s" (Prometheus counter)
   - "No-show predictions by risk level" (pie chart)
   - "IoT anomalies detected" (time series)
   - "Active RAG conversations" (gauge)
```

**Points à souligner :**
- BiLSTM 2 couches (128 hidden) + attention de Bahdanau
- Fenêtre 120 points × 4 features — normalisée par baseline patient
- Dégradé gracieux : si Kafka down → buffer CSV → réinjection automatique
- MLflow Registry alias `lstm-anomaly@champion`

---

## RGPD & Conformité (3 min)

**Message clé :** "Conformité RGPD article 30 — chiffrement AES-256, consentement granulaire, audit logs immuables, droit à l'effacement."

### Étapes

**4.1 Gestion du consentement**
```
→ Flutter app (ou interface web patient)
→ PATCH /api/v1/patients/me/consent
→ Montrer les toggles : "Partage anonymisé recherche", "Notifications SMS", "IoT monitoring"
→ "Consentement horodaté et signé, révocable à tout moment"
```

**4.2 Audit logs**
```
→ Admin → GET /api/v1/admin/audit-logs
→ Montrer : action, user_uuid, ip_hash, timestamp, resource
→ "Logs immuables — append-only, conformes Art.30"
```

**4.3 Export et suppression**
```
→ GET /api/v1/patients/{uuid}/data/export — télécharge JSON chiffré
→ DELETE /api/v1/patients/{uuid} — cascade anonymisation (pas de suppression physique)
→ "Droit à l'effacement : pseudonymisation, pas de suppression — cohérence ML préservée"
```

**4.4 Sécurité infrastructure**
```
→ Montrer nginx.conf : TLS 1.3 only, HSTS, rate limiting (auth 5/min, API 60/min)
→ OWASP ZAP : 0 High, 0 Medium dans CI (badge GitHub)
→ JWT blacklist Redis : révocation instantanée à la déconnexion
```

---

## Fallback Plan

Si Docker/services sont down le jour J :

**Option A — Screenshots préparés**
```
Dossier : docs/screenshots/
- demo_chat_darija.png
- demo_noshow_shap.png
- demo_iot_anomaly.png
- demo_grafana_dashboard.png
- demo_audit_logs.png
```

**Option B — Jupyter Notebook offline**
```bash
cd backend
jupyter notebook notebooks/demo_offline.ipynb
# Contient : RAG demo (texte), SHAP plots, LSTM inference sur données synthétiques
```

**Option C — Script CLI**
```bash
# Demo purement CLI sans Docker
cd backend
python scripts/smoke_test.py --base http://localhost:8000/api/v1
python scripts/train_lstm_anomaly.py --quick --epochs 5  # 2min
python scripts/detect_drift.py --dry-run
```

---

## Reset & Nettoyage

```bash
# Reset complet (entre deux runs de démo)
docker-compose down
docker volume rm medisense_postgres_data medisense_redis_data
docker-compose up -d
sleep 30
cd backend && python scripts/seed_admin.py

# Reset données uniquement (garde les services up)
cd backend && python -c "
import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models.user import User
from sqlalchemy import delete
asyncio.run(main())
"

# Vérification finale
python scripts/smoke_test.py
```

---

## Questions jury anticipées

| Question | Réponse courte |
|---|---|
| "Pourquoi XGBoost et pas un modèle deep learning pour le no-show ?" | "Données tabulaires + explainability SHAP + 10k samples — XGBoost est optimal. LSTM pour séries temporelles IoT." |
| "Comment gérez-vous la confidentialité des données d'entraînement ?" | "SDV + Faker — 100% synthétique, aucune donnée patient réelle. RGPD by design." |
| "Quelle est la latence du pipeline RAG ?" | "< 2s premier token en streaming. Groq cloud : ~300 tok/s. Ollama local : Metal GPU M1." |
| "Comment détectez-vous le Darija ?" | "Heuristique stopwords arabes courants + langdetect. Darija → traité comme Arabe." |
| "Kafka en production — comment gérez-vous les pannes ?" | "Dégradé gracieux : NoBrokersAvailable → buffer CSV /tmp/kafka-buffer/ → réinjection automatique à la reconnexion." |
| "Pourquoi MLflow et pas DVC ?" | "MLflow Registry + alias 'champion' permet l'auto-promotion et le rollback automatique sans infra supplémentaire." |
| "Coverage des tests ?" | "311 tests, 80% coverage gate en CI, 0 mock pour la DB (real PostgreSQL 16 en CI)." |
