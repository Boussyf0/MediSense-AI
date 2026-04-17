# MediSense AI — Méthodologie de Travail
**Rapport PFE 2025-2026 | Abderrahim Boussyf | EMSI Marrakech | n.synergy**

---

## Table des Matières

1. [Choix de la Méthode Agile](#1-choix-de-la-méthode-agile)
2. [Framework Scrum](#2-framework-scrum)
   - 2.1 Rôles
   - 2.2 Artefacts
   - 2.3 Cérémonies
   - 2.4 Cycle Scrum
3. [Product Backlog — Toutes les User Stories](#3-product-backlog--toutes-les-user-stories)
   - 3.1 Matrice MoSCoW
   - 3.2 Backlog complet par Sprint
4. [Planning des Sprints](#4-planning-des-sprints)
5. [Diagramme de Gantt](#5-diagramme-de-gantt)
6. [Vélocité & Story Points](#6-vélocité--story-points)
7. [Burndown Chart Global](#7-burndown-chart-global)
8. [Définition of Done (DoD)](#8-définition-of-done-dod)
9. [Gestion des Risques](#9-gestion-des-risques)
10. [Environnement & Outils de Travail](#10-environnement--outils-de-travail)
11. [Processus Git & CI/CD](#11-processus-git--cicd)
12. [Plan d'Implémentation — Objectif 10/10](#12-plan-dimplémentation--objectif-1010)

---

## 1. Choix de la Méthode Agile

### Pourquoi Agile plutôt que Cycle en V ?

Le projet MediSense AI combine **8 domaines techniques distincts** (IoT, LLM, ML, RGPD, DevOps, MLOps, CRM, Deep Learning) avec des exigences qui évoluent à mesure que les composants s'intègrent. Le cycle en V impose de geler les spécifications dès le début — incompatible avec un projet IA où les performances des modèles (F1, AUC-ROC) ne sont connues qu'après expérimentation.

| Critère | Cycle en V | Agile Scrum |
|---------|-----------|-------------|
| Spécifications figées | Requis | Non requis |
| Livraisons intermédiaires | Non | Oui (chaque sprint) |
| Adaptation aux résultats ML | Impossible | Naturelle |
| Feedback continu encadrant | Non | Oui (Sprint Review) |
| Gestion des risques techniques | Tardive | Continue |
| Convient aux projets IA | Non | **Oui** |

### Scrum vs Kanban vs SAFe

**Scrum** a été retenu car :
- Sprints de **2 semaines** correspondent à la granularité des livrables (1 pipeline = 1 sprint)
- Les **Sprint Reviews** permettent la validation de l'encadrant à chaque étape
- Le **Product Backlog** priorisé garantit que les fonctionnalités critiques (auth, RGPD) sont livrées en premier
- Adapté à un projet solo avec supervision externe (encadrant n.synergy)

---

## 2. Framework Scrum

### 2.1 Rôles

```mermaid
flowchart LR
    subgraph ROLES["Équipe Scrum — MediSense AI"]
        PO["👔 Product Owner<br/><br/>Encadrant n.synergy<br/>— Priorise le backlog<br/>— Valide les User Stories<br/>— Définit les critères d'acceptation<br/>— Représente les besoins métier"]

        SM["🔧 Scrum Master<br/><br/>Abderrahim Boussyf<br/>— Applique les pratiques Scrum<br/>— Lève les obstacles techniques<br/>— Anime les cérémonies<br/>— Garantit la DoD"]

        DEV["💻 Équipe de Développement<br/><br/>Abderrahim Boussyf<br/>— Conception architecture<br/>— Développement Backend (FastAPI)<br/>— Modèles ML/DL (XGBoost, LSTM)<br/>— Pipeline RAG (Qdrant + Mistral)<br/>— DevOps (Docker, GitHub Actions)<br/>— Tests (pytest ≥ 80% coverage)"]

        PROF["🎓 Jury / Encadrant EMSI<br/><br/>Professeur EMSI<br/>— Évalue le rapport PFE<br/>— Sprint Review finale<br/>— Soutenance"]
    end

    PO -->|"Backlog priorisé"| DEV
    SM -->|"Facilitation"| DEV
    DEV -->|"Démo sprint"| PO & PROF
```

---

### 2.2 Artefacts

```mermaid
flowchart TB
    subgraph ARTIFACTS["Artefacts Scrum"]
        PBL["📋 Product Backlog<br/><br/>— Liste ordonnée de toutes les US<br/>— Estimations en story points<br/>— Priorisation MoSCoW<br/>— 52 User Stories au total<br/>— Mis à jour chaque sprint"]

        SBL["📌 Sprint Backlog<br/><br/>— US sélectionnées pour le sprint<br/>— Décomposées en tâches techniques<br/>— Estimées en heures<br/>— Visible sur GitHub Projects<br/>— Propriété de l'équipe Dev"]

        INC["✅ Incrément<br/><br/>— Fonctionnalité livrable à la fin<br/>de chaque sprint<br/>— Respecte la DoD<br/>— Testée (pytest ≥ 80%)<br/>— Documentée (Swagger)<br/>— Mergée dans main via PR<br/>— Déployable à tout moment"]
    end

    PBL -->|"Sprint Planning"| SBL
    SBL -->|"Sprint 2 semaines"| INC
    INC -->|"Feedback"| PBL
```

---

### 2.3 Cérémonies

| Cérémonie | Durée | Fréquence | Participants | Livrable |
|-----------|-------|-----------|--------------|----------|
| **Sprint Planning** | 2h | Début de sprint | PO + Dev | Sprint Backlog validé |
| **Daily Standup** | 15min | Chaque jour | Dev (+ SM) | Rapport d'avancement |
| **Sprint Review** | 1h | Fin de sprint | PO + Dev + Jury | Démo du produit fonctionnel |
| **Sprint Retrospective** | 30min | Fin de sprint | Dev + SM | Plan d'amélioration |
| **Backlog Refinement** | 1h | Mi-sprint | PO + Dev | Backlog affiné et estimé |

---

### 2.4 Cycle Scrum

```mermaid
flowchart LR
    PBL["📋 Product Backlog<br/>(52 US priorisées)"]

    subgraph SPRINT["🔄 Sprint — 2 Semaines"]
        direction TB
        PLAN["Sprint Planning<br/>Sélection des US<br/>+ décomposition tâches"]
        DEV_W["Développement<br/>Daily Standup quotidien<br/>Intégration continue"]
        REVIEW["Sprint Review<br/>Démo à l'encadrant<br/>Validation US"]
        RETRO["Rétrospective<br/>What went well?<br/>What to improve?"]
        PLAN --> DEV_W --> REVIEW --> RETRO
    end

    INC["✅ Incrément<br/>Fonctionnel<br/>Testé<br/>Documenté<br/>Mergé → main"]

    PBL -->|"Sprint Backlog"| SPRINT
    SPRINT --> INC
    INC -->|"Feedback →<br/>Mise à jour backlog"| PBL
```

---

## 3. Product Backlog — Toutes les User Stories

### 3.1 Matrice MoSCoW

```mermaid
flowchart TB
    subgraph MUST["🔴 Must Have — Non négociable"]
        M1["US-01 Infrastructure Docker 6 services"]
        M2["US-02 HTTPS TLS 1.3 + OWASP"]
        M3["US-03 Authentification JWT + Redis"]
        M4["US-04 RBAC 4 rôles"]
        M5["US-05 Schéma RGPD + AES-256"]
        M6["US-06 Consentement granulaire"]
        M7["US-08 Droit à l'effacement"]
        M8["US-09 LLM Mistral 7B < 150ms"]
        M9["US-10 84k chunks Qdrant"]
        M10["US-11 Chatbot FR/AR/Darija"]
        M11["US-17 Feature engineering No-Show"]
        M12["US-18 Modèle XGBoost F1 > 0.80"]
        M13["US-25 Kafka IoT 10 msg/s"]
        M14["US-27 LSTM AUC-ROC > 0.85"]
        M15["US-47 Flutter app patient — auth + onboarding RGPD"]
        M16["US-48 Flutter chatbot Darija/FR + input vocal"]
        M17["US-51 Next.js dashboard médecin — fondation"]
    end

    subgraph SHOULD["🟠 Should Have — Important"]
        S1["US-07 Export données RGPD"]
        S2["US-12 Cross-encoder re-ranking"]
        S3["US-13 Contexte IoT dans chat"]
        S4["US-14 Orchestrateur agents"]
        S5["US-19 Agenda code couleur"]
        S6["US-20 Predict No-Show < 200ms"]
        S7["US-24 Webhook Salesforce"]
        S8["US-26 TimescaleDB hypertable"]
        S9["US-28 Détection 2 fenêtres"]
        S10["US-29 Push notification réveil"]
        S11["US-33 MLflow Model Registry"]
        S12["US-37 CI/CD GitHub Actions"]
        S13["US-41 Vue DPA 3 colonnes"]
        S14["US-45 Swagger UI /docs"]
        S15["US-46 Endpoint audit logs"]
        S16["US-49 Flutter IoT dashboard FC/SpO2/HRV"]
        S17["US-50 Flutter prise de RDV + sync Salesforce"]
        S18["US-52 DPA UI 3 colonnes IoT/Symptômes/IA"]
        S19["US-53 Smart Agenda UI code couleur no-show"]
        S20["US-54 WebSocket alertes + modal Twilio VOIP"]
        S21["US-55 Flutter résultats analyses + LLM"]
        S22["US-56 FCM push J-3/J-1/H-2"]
        S23["US-57 Grafana 3 dashboards monitoring"]
        S24["US-60 Admin UI — audit logs + user management"]
    end

    subgraph COULD["🟡 Could Have — Souhaitable"]
        C1["US-15 Mémoire Redis 24h"]
        C2["US-22 SMOTE rééquilibrage"]
        C3["US-30 Mode dégradé Kafka"]
        C4["US-34 Airflow réentraînement"]
        C5["US-35 Evidently AI drift"]
        C6["US-38 OWASP ZAP scan"]
        C7["US-42 Human-in-the-Loop"]
        C8["US-43 Tâches Salesforce"]
        C9["US-58 Salesforce Apex Trigger code"]
        C10["US-59 Flutter ordonnances + rappels médicaments"]
    end

    subgraph WONT["⚪ Won't Have (hors scope PFE)"]
        W1["Multi-tenant (plusieurs cliniques)"]
        W2["Intégration HL7 FHIR"]
        W3["Application smartwatch native (WatchOS/WearOS)"]
    end
```

---

### 3.2 Backlog Complet par Sprint

#### Sprint 1 — Fondation & Authentification `30 Mar – 12 Avr 2026` `✅ TERMINÉ`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-01 | `docker compose up` lance 6 services. `/health` répond 200 en < 2s | 5 | Must | ✅ Done |
| US-02 | HTTPS sur tous les endpoints. TLS 1.3 via nginx. Headers OWASP | 5 | Must | ✅ Done |
| US-03 | OAuth2/JWT : access token (15min) + refresh (7j) + révocation Redis | 8 | Must | ✅ Done |
| US-04 | RBAC : 4 rôles (patient, doctor, secretary, admin). Non autorisé → 403 | 5 | Must | ✅ Done |
| US-05 | Schéma RGPD : patients UUID pseudonymisés + identité AES-256 | 8 | Must | ✅ Done |
| US-45 | Swagger auto-docs à `/api/v1/docs` (assets locaux, no CDN) | 3 | Should | ✅ Done |
| **Total** | | **34 pts** | | |

#### Sprint 2 — RGPD & Consentement `01 Avr – 14 Avr 2026` `✅ TERMINÉ`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-06 | Consentement granulaire : 3 opt-ins séparés (IoT / NLP / Partage) | 5 | Must | ⏳ |
| US-07 | Export données patient : `GET /patient/data/export` JSON complet (Art.15) | 5 | Should | ⏳ |
| US-08 | Droit à l'effacement : `DELETE /patient/{uuid}` + cascade Qdrant (Art.17) | 8 | Must | ⏳ |
| US-46 | Endpoint audit logs paginé : `GET /admin/audit-logs` (Art.30) | 3 | Should | ⏳ |
| **Total** | | **21 pts** | | |

#### Sprint 3 — RAG Pipeline & LLM `15 Avr – 28 Avr 2026` `✅ TERMINÉ`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-09 | Mistral 7B via Ollama. Latence retrieval P95 = 265 ms (CPU) | 8 | Must | ✅ Done |
| US-10 | Indexer 96 303 pts Qdrant (ICD-10, BDPM France, medicament.ma, corpus offline) | 13 | Must | ✅ Done |
| US-11 | Chatbot symptômes FR/AR/Darija avec triage cognitif + 141 SAMU Maroc | 8 | Must | ✅ Done |
| US-12 | Hybrid Dense+BM25+RRF, safety layer code-level, red-team 10 cas | 5 | Should | ✅ Done |
| **Total** | | **34 pts** | | |

#### Sprint 4 — Agents IA & DPA `11 Mai – 24 Mai 2026` `⏳ À venir`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-13 | Contexte IoT injecté dans le chat patient (anomalies → RAG) | 8 | Should | ⏳ |
| US-14 | Orchestrateur multi-agents (triage → RDV → CRM) | 13 | Should | ⏳ |
| US-15 | Mémoire de conversation Redis TTL 24h (multi-session) | 3 | Could | ⏳ |
| US-41 | Vue DPA médecin : résumé 3 colonnes (Symptômes / IoT / Actions) | 8 | Should | ⏳ |
| US-42 | Human-in-the-Loop : médecin valide/modifie le résumé IA | 5 | Could | ⏳ |
| **Total** | | **37 pts** | | |

#### Sprint 5 — ML Prédictif No-Show `25 Mai – 07 Jun 2026` `⏳ À venir`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-17 | Feature engineering : 8 features patient (distance, météo, historique...) | 5 | Must | ⏳ |
| US-18 | Entraîner XGBoost vs LightGBM vs CatBoost. F1 cible > 0.80 | 13 | Must | ⏳ |
| US-19 | Agenda code couleur : 🔴 > 70% / 🟠 40-70% / 🟢 < 40% | 5 | Should | ⏳ |
| US-20 | Endpoint `POST /predict/noshow` réponse < 200ms | 3 | Should | ⏳ |
| US-22 | SMOTE sur données déséquilibrées (no-show < 20% des RDV) | 5 | Could | ⏳ |
| **Total** | | **31 pts** | | |

#### Sprint 6 — Salesforce & MLOps `08 Jun – 21 Jun 2026` `⏳ À venir`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-24 | Webhook Salesforce Apex : tâche secrétaire créée automatiquement | 8 | Should | ⏳ |
| US-33 | MLflow Model Registry : versioning + métriques + artefacts SHAP | 5 | Should | ⏳ |
| US-37 | GitHub Actions CI/CD : build → test → push image → deploy | 8 | Should | ⏳ |
| US-38 | OWASP ZAP scan automatisé (rapport vulnérabilités) | 5 | Could | ⏳ |
| US-43 | Interface secrétaire : gestion tâches Salesforce (confirmer, clôturer) | 3 | Could | ⏳ |
| **Total** | | **29 pts** | | |

#### Sprint 7 — IoT Pipeline & LSTM `22 Jun – 05 Juil 2026` `⏳ À venir`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-25 | Ingestion Kafka biométriques : 10 msg/s en débit continu | 8 | Must | ⏳ |
| US-26 | TimescaleDB hypertable : partitionnement par jour, compression auto | 5 | Should | ⏳ |
| US-27 | LSTM Bidirectionnel PyTorch : AUC-ROC > 0.85 sur données synthétiques | 13 | Must | ⏳ |
| US-28 | Détection sur 2 fenêtres glissantes : 5min (critique) + 60min (tendance) | 8 | Should | ⏳ |
| US-29 | Push notification au réveil (détection accéléromètre) | 5 | Should | ⏳ |
| **Total** | | **39 pts** | | |

#### Sprint 8 — Intégration & Production `06 Juil – 19 Juil 2026` `⏳ À venir`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-30 | Mode dégradé Kafka : buffer local + reprise automatique à reconnexion | 8 | Could | ⏳ |
| US-34 | DAG Airflow : réentraînement hebdomadaire automatique | 8 | Could | ⏳ |
| US-35 | Evidently AI : détection dérive données (PSI + feature importance shift) | 5 | Could | ⏳ |
| US-36 | Auto-rollback : si F1 chute > 10% en prod → restauration version N-1 | 5 | Could | ⏳ |
| **Total** | | **26 pts** | | |

#### Sprint 9 — Application Mobile Patient (Flutter) `20 Juil – 02 Aoû 2026` `⏳ À venir`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-47 | Flutter — Onboarding 3 slides + auth JWT + consentement RGPD UI (opt-in IoT/NLP/Partage) | 5 | Must | ⏳ |
| US-48 | Flutter — Chatbot triage Darija/FR/AR avec input vocal (STT) + contexte IoT pré-chargé | 8 | Must | ⏳ |
| US-49 | Flutter — Dashboard IoT personnel : courbes FC/SpO2/HRV sur 7/30/90 jours (charts animés) | 8 | Should | ⏳ |
| US-50 | Flutter — Prise de RDV en ligne avec calendrier temps réel + sync Salesforce | 5 | Should | ⏳ |
| US-55 | Flutter — Résultats d'analyses avec interprétation LLM simplifiée (Mistral 7B) | 5 | Should | ⏳ |
| US-56 | FCM push notifications : rappels automatiques J-3, J-1, H-2 (Firebase Cloud Messaging) | 5 | Should | ⏳ |
| US-59 | Flutter — Ordonnances numériques + rappels médicaments (heure + dosage) | 3 | Could | ⏳ |
| **Total** | | **39 pts** | | |

#### Sprint 10 — Dashboard Médecin (Next.js) + Monitoring (Grafana) `03 Aoû – 16 Aoû 2026` `⏳ À venir`

| ID | User Story | Story Points | Priorité | Statut |
|----|-----------|:---:|:---:|:---:|
| US-51 | Next.js — Fondation dashboard médecin : auth, routing, layout sidebar, AuthGuard RBAC | 5 | Must | ⏳ |
| US-52 | DPA UI — Vue 3 colonnes : IoT anomaly graphs \| NLP symptoms verbatim \| RAG suggestions IA | 8 | Should | ⏳ |
| US-53 | Smart Agenda UI — code couleur no-show 🟢 <20% / 🟠 20–40% / 🔴 >40% + créneaux remplacement | 5 | Should | ⏳ |
| US-54 | WebSocket alertes IoT temps réel + modal popup + bouton "Appeler patient" (Twilio VOIP) | 8 | Should | ⏳ |
| US-57 | Grafana — 3 dashboards provisionnés : System Health / ML Performance / Business KPIs | 5 | Should | ⏳ |
| US-60 | Admin UI — audit logs viewer paginé + filtres + user management (Next.js pages admin) | 5 | Should | ⏳ |
| US-58 | Salesforce Apex Trigger code (côté CRM) + payload types partagés | 3 | Could | ⏳ |
| **Total** | | **39 pts** | | |

---

## 4. Planning des Sprints

```mermaid
flowchart TB
    subgraph PLAN["Planning Global — 10 Sprints / 5 Mois"]
        direction LR

        subgraph S1["Sprint 1<br/>30 Mar – 12 Avr<br/>✅ TERMINÉ"]
            T1["Infrastructure Docker<br/>Auth JWT + RBAC<br/>Schéma RGPD<br/>Swagger UI<br/>34 pts"]
        end

        subgraph S2["Sprint 2<br/>13 Avr – 26 Avr<br/>⏳ En cours"]
            T2["Consentement granulaire<br/>Export RGPD<br/>Droit à l'effacement<br/>Audit logs endpoint<br/>21 pts"]
        end

        subgraph S3["Sprint 3<br/>27 Avr – 10 Mai<br/>⏳ À venir"]
            T3["Mistral 7B Ollama<br/>84k chunks Qdrant<br/>Chatbot FR/AR/Darija<br/>Cross-encoder<br/>34 pts"]
        end

        subgraph S4["Sprint 4<br/>11 Mai – 24 Mai<br/>⏳ À venir"]
            T4["Contexte IoT chat<br/>Orchestrat. agents<br/>Mémoire Redis<br/>DPA 3 colonnes<br/>Human-in-Loop<br/>37 pts"]
        end

        subgraph S5["Sprint 5<br/>25 Mai – 07 Jun<br/>⏳ À venir"]
            T5["Feature engineering<br/>XGBoost vs LGB<br/>Agenda couleur<br/>Predict endpoint<br/>SMOTE<br/>31 pts"]
        end

        subgraph S6["Sprint 6<br/>08 Jun – 21 Jun<br/>⏳ À venir"]
            T6["Salesforce webhook<br/>MLflow Registry<br/>CI/CD Actions<br/>OWASP ZAP<br/>29 pts"]
        end

        subgraph S7["Sprint 7<br/>22 Jun – 05 Juil<br/>⏳ À venir"]
            T7["Kafka ingestion<br/>TimescaleDB<br/>LSTM AUC > 0.85<br/>2 fenêtres détect.<br/>Push notif.<br/>39 pts"]
        end

        subgraph S8["Sprint 8<br/>06 Juil – 19 Juil<br/>⏳ À venir"]
            T8["Mode dégradé Kafka<br/>Airflow DAG<br/>Evidently drift<br/>Auto-rollback<br/>26 pts"]
        end

        subgraph S9["Sprint 9<br/>20 Juil – 02 Aoû<br/>⏳ À venir"]
            T9["Flutter app patient<br/>Onboarding + Auth<br/>Chatbot vocal<br/>IoT dashboard<br/>FCM push notif.<br/>39 pts"]
        end

        subgraph S10["Sprint 10<br/>03 Aoû – 16 Aoû<br/>⏳ À venir"]
            T10["Next.js dashboard<br/>DPA 3 colonnes UI<br/>Smart Agenda UI<br/>WebSocket + Twilio<br/>Grafana dashboards<br/>39 pts"]
        end

        subgraph FIN["Finalisation<br/>17 Aoû – 31 Aoû"]
            T11["Rédaction rapport<br/>Préparation soutenance<br/>Tests intégration<br/>Démonstration"]
        end

        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10 --> FIN
    end
```

---

## 5. Diagramme de Gantt

```mermaid
gantt
    title MediSense AI — Planning Agile 10 Sprints (Mar 2026 – Sep 2026)
    dateFormat  YYYY-MM-DD
    axisFormat  %d %b

    section Fondation
    Sprint 1 — Infrastructure & Auth          :done,    s1, 2026-03-30, 2026-04-12

    section RGPD
    Sprint 2 — Consentement & Effacement      :active,  s2, 2026-04-13, 2026-04-26

    section IA Conversationnelle
    Sprint 3 — RAG Pipeline & Mistral 7B      :         s3, 2026-04-27, 2026-05-10
    Sprint 4 — Agents IA & DPA Médecin        :         s4, 2026-05-11, 2026-05-24

    section ML Prédictif
    Sprint 5 — No-Show XGBoost                :         s5, 2026-05-25, 2026-06-07

    section MLOps & CRM
    Sprint 6 — Salesforce & MLflow & CI/CD    :         s6, 2026-06-08, 2026-06-21

    section IoT & Deep Learning
    Sprint 7 — Kafka & LSTM Anomalie          :         s7, 2026-06-22, 2026-07-05

    section Production
    Sprint 8 — Intégration & Résilience       :         s8, 2026-07-06, 2026-07-19

    section Frontend Mobile
    Sprint 9 — Flutter App Patient            :         s9, 2026-07-20, 2026-08-02

    section Frontend Web & Monitoring
    Sprint 10 — Dashboard Médecin + Grafana   :         s10, 2026-08-03, 2026-08-16

    section Rapport PFE
    Rédaction rapport & soutenance            :crit,    rpt, 2026-08-17, 2026-08-31

    section Jalons
    Gate Review S1+S2 — Fondation & RGPD     :milestone, g2, 2026-04-26, 0d
    Gate Review S3+S4 — RAG & Agents IA      :milestone, g4, 2026-05-24, 0d
    Gate Review S5+S6 — ML & MLOps           :milestone, g6, 2026-06-21, 0d
    Gate Review S7+S8 — IoT & Production     :milestone, g8, 2026-07-19, 0d
    Gate Review S9+S10 — Frontend complet    :milestone, g10, 2026-08-16, 0d
    Soutenance PFE                            :milestone, sout, 2026-08-31, 0d
```

---

## 6. Vélocité & Story Points

### Résumé par Sprint

```mermaid
xychart-beta
    title "Story Points par Sprint"
    x-axis ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]
    y-axis "Story Points" 0 --> 45
    bar  [34, 21, 34, 37, 31, 29, 39, 26, 39, 39]
    line [34, 21, 34, 37, 31, 29, 39, 26, 39, 39]
```

### Tableau Récapitulatif

| Sprint | Durée | User Stories | Story Points | Complexité dominante |
|--------|-------|:---:|:---:|---|
| Sprint 1 | 2 sem. | 6 US | 34 pts | Infrastructure / Sécurité |
| Sprint 2 | 2 sem. | 4 US | 21 pts | Conformité RGPD |
| Sprint 3 | 2 sem. | 4 US | 34 pts | RAG / Indexation / LLM |
| Sprint 4 | 2 sem. | 5 US | 37 pts | Agents IA / Orchestration |
| Sprint 5 | 2 sem. | 5 US | 31 pts | ML / Feature Engineering |
| Sprint 6 | 2 sem. | 5 US | 29 pts | MLOps / CRM / DevOps |
| Sprint 7 | 2 sem. | 5 US | 39 pts | IoT / Deep Learning |
| Sprint 8 | 2 sem. | 4 US | 26 pts | Résilience / Production |
| Sprint 9 | 2 sem. | 7 US | 39 pts | Flutter Mobile / FCM / IoT UI |
| Sprint 10 | 2 sem. | 7 US | 39 pts | Next.js Dashboard / Grafana / Twilio |
| **TOTAL** | **20 sem.** | **52 US** | **329 pts** | |

> **Vélocité moyenne :** 32.9 story points / sprint
> **Estimation :** Fibonacci modifiée — 1, 2, 3, 5, 8, 13 points

---

## 7. Burndown Chart Global

```mermaid
xychart-beta
    title "Burndown Chart Global — 329 Story Points"
    x-axis ["Début", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]
    y-axis "Points restants" 0 --> 340
    line [329, 295, 274, 240, 203, 172, 143, 104, 78, 39, 0]
```

> **Ligne idéale :** décroissance linéaire de 329 → 0 sur 10 sprints.
> **Lecture :** après Sprint 1 (34 pts livrés), il reste 295 pts. Sprints 9 & 10 couvrent le frontend complet (Flutter + Next.js + Grafana — 78 pts). La courbe doit rester proche de la ligne idéale pour garantir la livraison avant soutenance.

---

## 8. Définition of Done (DoD)

La DoD est le contrat de qualité entre le Product Owner et l'équipe. **Une User Story n'est "Done" que si tous les critères sont satisfaits.**

```mermaid
flowchart TD
    START["User Story développée"] --> C1

    C1{"Code reviewé<br/>(GitHub PR + Copilot AI)"}
    C1 -->|Non| FIX1["Corriger les remarques<br/>de code review"]
    C1 -->|Oui| C2

    C2{"Tests unitaires<br/>pytest ≥ 80% coverage"}
    C2 -->|Non| FIX2["Écrire les tests manquants"]
    C2 -->|Oui| C3

    C3{"Endpoint documenté<br/>dans Swagger UI"}
    C3 -->|Non| FIX3["Ajouter docstring<br/>et schéma Pydantic"]
    C3 -->|Oui| C4

    C4{"Aucune régression<br/>CI/CD GitHub Actions vert"}
    C4 -->|Non| FIX4["Corriger la régression"]
    C4 -->|Oui| C5

    C5{"Sécurité vérifiée<br/>(OWASP, JWT, RBAC)"}
    C5 -->|Non| FIX5["Corriger la vulnérabilité"]
    C5 -->|Oui| C6

    C6{"RGPD respecté<br/>(audit log, consentement vérifié)"}
    C6 -->|Non| FIX6["Ajouter audit log<br/>ou vérif. consentement"]
    C6 -->|Oui| C7

    C7{"Performance validée<br/>(P95 < SLA défini)"}
    C7 -->|Non| FIX7["Optimiser / profiler"]
    C7 -->|Oui| C8

    C8{"Mergée dans branch sprint<br/>via PR approuvée"}
    C8 -->|Non| FIX8["Créer la PR"]
    C8 -->|Oui| DONE["✅ User Story DONE"]

    FIX1 & FIX2 & FIX3 & FIX4 & FIX5 & FIX6 & FIX7 & FIX8 --> START
```

### Critères DoD par Catégorie

| Catégorie | Critère | Mesure |
|-----------|---------|--------|
| **Code** | Revue par Copilot AI + auto-review | PR approuvée |
| **Tests** | Couverture pytest | ≥ 80% (rapport `--cov`) |
| **API** | Documentation Swagger | Schémas Pydantic complets |
| **CI/CD** | Pipeline GitHub Actions | Tous checks verts |
| **Sécurité** | Pas de secret en dur, RBAC validé | OWASP check |
| **RGPD** | Audit log inséré, consentement vérifié | Log visible `/admin/audit-logs` |
| **Performance** | Latence P95 | Auth < 500ms, RAG < 150ms, ML < 200ms |
| **Git** | Branche sprint, PR vers main | Branch `sprint/N-*` mergée |

---

## 9. Gestion des Risques

### 9.1 Registre des Risques

| ID | Catégorie | Risque | Probabilité (P) | Impact (I) | Score P×I | Criticité |
|----|-----------|--------|:---:|:---:|:---:|:---:|
| R-01 | Technique IA | Latence Mistral 7B > 150ms en local | 4 | 4 | **16** | 🔴 Critique |
| R-02 | Technique ML | F1-Score XGBoost < 0.80 (no-show) | 3 | 5 | **15** | 🔴 Critique |
| R-03 | Données | Données patients insuffisantes / non réalistes | 4 | 5 | **20** | 🔴 Critique |
| R-04 | Technique DL | AUC-ROC LSTM < 0.85 (anomalie IoT) | 3 | 4 | **12** | 🟠 Élevé |
| R-05 | Conformité | Fuite de données personnelles (RGPD) | 1 | 5 | **5** | 🟠 Élevé |
| R-06 | MLOps | Dérive du modèle en production | 4 | 3 | **12** | 🟠 Élevé |
| R-07 | Infrastructure | RAM insuffisante pour Ollama + Stack Docker | 3 | 3 | **9** | 🟡 Modéré |
| R-08 | Infrastructure | Indisponibilité Kafka (streaming IoT) | 2 | 3 | **6** | 🟡 Modéré |
| R-09 | Intégration | Webhook Salesforce rejeté (auth, quota) | 2 | 2 | **4** | 🟢 Faible |
| R-10 | Sécurité | Vulnérabilité OWASP non détectée | 2 | 4 | **8** | 🟡 Modéré |
| R-11 | Planning | Retard d'un sprint (sous-estimation) | 3 | 3 | **9** | 🟡 Modéré |
| R-12 | Technique | Incompatibilité version librairie ML | 2 | 2 | **4** | 🟢 Faible |

> **Échelle :** Probabilité et Impact de 1 (très faible) à 5 (très élevé). Score = P × I. Seuils : ≥ 12 🔴 Critique, 6–11 🟠/🟡 Modéré–Élevé, ≤ 5 🟢 Faible.

---

### 9.2 Matrice Probabilité × Impact

```mermaid
flowchart TB
    subgraph MATRIX["Matrice des Risques — MediSense AI"]
        direction TB

        subgraph ROW5["Impact 5 — Catastrophique"]
            C5_1["🟡 P=1<br/>R-05<br/>Fuite RGPD"]
            C5_3["🔴 P=3<br/>R-02 F1 XGBoost<br/>R-04 LSTM AUC"]
            C5_4["🔴 P=4<br/>R-03 Données<br/>insuffisantes"]
        end

        subgraph ROW4["Impact 4 — Critique"]
            C4_1["🟢 P=1<br/>—"]
            C4_2["🟡 P=2<br/>R-10 OWASP"]
            C4_3["🟠 P=3<br/>—"]
            C4_4["🔴 P=4<br/>R-01 Latence<br/>Mistral 7B"]
        end

        subgraph ROW3["Impact 3 — Significatif"]
            C3_2["🟢 P=2<br/>R-08 Kafka"]
            C3_3["🟡 P=3<br/>R-07 RAM Ollama<br/>R-11 Retard sprint"]
            C3_4["🟠 P=4<br/>R-06 Derive<br/>modele prod"]
        end

        subgraph ROW2["Impact 2 — Mineur"]
            C2_2["🟢 P=2<br/>R-09 Salesforce<br/>R-12 Versions"]
            C2_3["🟢 P=3<br/>—"]
        end
    end

    subgraph LEGENDE["Légende"]
        L1["🔴 Score ≥ 12 — Critique : action immédiate"]
        L2["🟠 Score 8-11 — Élevé : plan de mitigation requis"]
        L3["🟡 Score 5-7 — Modéré : surveiller"]
        L4["🟢 Score ≤ 4 — Faible : accepter"]
    end
```

---

### 9.3 Plan de Mitigation Détaillé

#### R-01 — Latence Mistral 7B > 150ms `🔴 Critique`

```mermaid
flowchart LR
    RISK["⚠️ R-01<br/>Latence RAG > 150ms<br/>P=4 I=4 Score=16"]

    subgraph PREVENT["Prévention"]
        P1["Modèle quantifié<br/>Mistral 7B Q4_K_M<br/>(4.1 GB RAM)"]
        P2["Cache Redis<br/>réponses fréquentes<br/>TTL 1h"]
        P3["Prompt engineering<br/>réduit les tokens<br/>de génération"]
    end

    subgraph CONTINGENCY["Plan de Secours"]
        C1["Fallback automatique<br/>vers Mistral API Cloud<br/>(paiement à l'usage)"]
        C2["Mode dégradé :<br/>réponses prédéfinies<br/>pour cas fréquents"]
    end

    subgraph MONITOR["Surveillance"]
        M1["Mesure latence P95<br/>à chaque requête"]
        M2["Alerte si P95 > 120ms<br/>(seuil préventif)"]
    end

    RISK --> PREVENT & CONTINGENCY & MONITOR
```

---

#### R-02 — F1-Score XGBoost < 0.80 `🔴 Critique`

```mermaid
flowchart LR
    RISK["⚠️ R-02<br/>F1 No-Show < 0.80<br/>P=3 I=5 Score=15"]

    subgraph PREVENT["Prévention"]
        P1["SMOTE : rééquilibrage<br/>classes déséquilibrées<br/>(no-show < 20%)"]
        P2["Ensemble 3 modèles :<br/>XGBoost + LightGBM<br/>+ CatBoost (vote)"]
        P3["Optuna : tuning<br/>hyperparamètres<br/>100 trials"]
        P4["SHAP : validation<br/>que les features<br/>sont pertinentes"]
    end

    subgraph CONTINGENCY["Plan de Secours"]
        C1["Abaisser le seuil<br/>de criticité (ex: F1>0.75)<br/>avec justification"]
        C2["Règles métier manuelles<br/>en complément du ML<br/>(fallback statistique)"]
    end

    RISK --> PREVENT & CONTINGENCY
```

---

#### R-03 — Données Patients Insuffisantes `🔴 Critique (Score=20)`

```mermaid
flowchart LR
    RISK["⚠️ R-03<br/>Donnees insuffisantes<br/>P=4 I=5 Score=20"]

    subgraph SOURCES["Sources de Données"]
        S1["Synthea<br/>Dossiers patients<br/>synthétiques réalistes"]
        S2["MIMIC-IV<br/>Données ICU<br/>(sous licence)"]
        S3["PhysioNet<br/>Données biométriques<br/>validées cliniquement"]
        S4["Faker + règles métier<br/>Génération cohérente<br/>(no-show corrélé<br/>à distance, météo...)"]
    end

    subgraph VALIDATION["Validation"]
        V1["Expert métier<br/>valide la distribution<br/>des données générées"]
        V2["Tests statistiques<br/>(KS-test vs données<br/>réelles anonymisées)"]
    end

    RISK --> SOURCES & VALIDATION
```

---

#### R-04 — AUC-ROC LSTM < 0.85 `🟠 Élevé`

```mermaid
flowchart LR
    RISK["⚠️ R-04<br/>LSTM AUC < 0.85<br/>P=3 I=4 Score=12"]

    subgraph PREVENT["Prévention"]
        P1["Architecture :<br/>LSTM Bidirectionnel<br/>+ couche Attention"]
        P2["Data augmentation :<br/>jitter temporel,<br/>time-warp, cropping"]
        P3["2 fenêtres :<br/>5min (critique)<br/>60min (tendance)"]
        P4["Transfer learning<br/>PhysioNet pré-entrainé"]
    end

    subgraph CONTINGENCY["Plan de Secours"]
        C1["Isolation Forest<br/>algorithme de secours<br/>(non supervisé)"]
        C2["Abaisser seuil<br/>à AUC > 0.80<br/>si données limitées"]
    end

    RISK --> PREVENT & CONTINGENCY
```

---

#### R-05 — Fuite Données RGPD `🟠 Élevé (Impact=5)`

```mermaid
flowchart TB
    RISK["⚠️ R-05<br/>Fuite donnees RGPD<br/>P=1 I=5 Score=5"]

    subgraph LAYERS["Défense en Profondeur"]
        L1["Couche Transport<br/>TLS 1.3 obligatoire<br/>HSTS 1 an"]
        L2["Couche Auth<br/>JWT + Redis blacklist<br/>bcrypt rounds=12"]
        L3["Couche Donnees<br/>AES-256 pgcrypto<br/>schema secure separe"]
        L4["Couche Acces<br/>RBAC strict<br/>audit_log immuable"]
        L5["Couche Scan<br/>OWASP ZAP<br/>CI/CD automatique"]
    end

    subgraph RESPONSE["Plan de Réponse (si fuite)"]
        R1["Notification CNIL<br/>< 72h (Art. 33 RGPD)"]
        R2["Notification patients<br/>concernés (Art. 34)"]
        R3["Révocation tokens<br/>Redis flush"]
        R4["Audit forensique<br/>des audit_logs"]
    end

    RISK --> LAYERS & RESPONSE
```

---

#### R-06 — Dérive du Modèle en Production `🟠 Élevé`

```mermaid
flowchart LR
    RISK["⚠️ R-06<br/>Derive modele prod<br/>P=4 I=3 Score=12"]

    subgraph DETECT["Détection — Evidently AI"]
        D1["Rapport hebdomadaire<br/>PSI (Population<br/>Stability Index)"]
        D2["Feature importance<br/>shift monitoring"]
        D3["Métriques prod :<br/>F1, précision, rappel<br/>vs baseline"]
    end

    subgraph RESPONSE["Réponse Automatique — Airflow"]
        R1["DAG hebdomadaire :<br/>réentraînement<br/>autonome"]
        R2["Si F1 ameliore > 1% :<br/>promotion MLflow<br/>→ production"]
        R3["Si F1 chute > 10% :<br/>auto-rollback<br/>version N-1"]
    end

    RISK --> DETECT --> RESPONSE
```

---

### 9.4 Processus de Suivi des Risques

```mermaid
flowchart TD
    IDENT["📋 Identification<br/>Début de chaque sprint :<br/>revoir le registre des risques"]

    EVAL["📊 Évaluation<br/>Réévaluer P et I<br/>selon l'avancement"]

    TRIAGE{"Score ≥ 12?<br/>(Risque Critique)"}

    ACTION_IMM["🔴 Action Immédiate<br/>Mitigation dans le sprint courant<br/>Signalement encadrant"]

    PLAN_MIT["🟠 Plan de Mitigation<br/>Planifier dans le sprint suivant<br/>Surveillance renforcée"]

    SURVEILLER["🟡 Surveiller<br/>Point en rétrospective<br/>Pas d'action urgente"]

    ACCEPTER["🟢 Accepter<br/>Log dans le registre<br/>Réévaluation mensuelle"]

    UPDATE["🔄 Mise à jour<br/>Registre des risques<br/>(GitHub Issues/Projects)"]

    IDENT --> EVAL --> TRIAGE
    TRIAGE -->|Oui| ACTION_IMM --> UPDATE
    TRIAGE -->|Non Score 8-11| PLAN_MIT --> UPDATE
    TRIAGE -->|Non Score 5-7| SURVEILLER --> UPDATE
    TRIAGE -->|Non Score ≤ 4| ACCEPTER --> UPDATE
    UPDATE -->|Sprint suivant| IDENT
```

---

## 10. Environnement & Outils de Travail

```mermaid
flowchart TB
    subgraph DEV["Environnement de Développement"]
        subgraph IDE["IDE & Éditeur"]
            VS["VS Code<br/>+ Extensions:<br/>Python, Docker,<br/>Mermaid Preview,<br/>GitLens, Copilot"]
        end

        subgraph LANG["Langages"]
            PY["Python 3.11<br/>Language principal"]
            SQL["SQL<br/>PostgreSQL, migrations"]
            YAML["YAML<br/>Docker Compose, CI/CD"]
            BASH["Bash<br/>Scripts init, certs"]
        end

        subgraph LOCAL["Stack Locale"]
            DOCK["Docker Desktop<br/>Mac (Apple Silicon)"]
            GIT["Git 2.x<br/>branches sprint/N-*"]
        end
    end

    subgraph FRAMEWORKS["Frameworks & Librairies"]
        subgraph BACKEND["Backend"]
            FA["FastAPI 0.115<br/>Uvicorn 0.32<br/>SQLAlchemy 2.0<br/>Alembic 1.14<br/>Pydantic v2"]
        end
        subgraph ML_LIB["ML / DL"]
            ML["XGBoost<br/>LightGBM<br/>CatBoost<br/>Scikit-learn<br/>SHAP"]
            DL["PyTorch<br/>LSTM Bidirectionnel"]
        end
        subgraph RAG_LIB["RAG"]
            RA["Sentence-Transformers<br/>Qdrant Client<br/>Ollama Python SDK<br/>Cross-Encoder"]
        end
    end

    subgraph INFRA["Infrastructure"]
        subgraph DB_STACK["Bases de Données"]
            PG2["PostgreSQL 16<br/>+ pgcrypto"]
            RD["Redis 7<br/>AOF + Auth"]
            QD["Qdrant<br/>Vecteur DB"]
            TS2["TimescaleDB<br/>Séries temporelles"]
        end
        subgraph STREAM["Streaming"]
            KFK["Apache Kafka<br/>+ ZooKeeper"]
        end
        subgraph PROXY["Proxy / Sécurité"]
            NGX["Nginx Alpine<br/>TLS 1.3"]
        end
        subgraph AI_INFRA["IA Locale"]
            OLL["Ollama<br/>Mistral 7B Q4_K_M"]
        end
    end

    subgraph DEVOPS["DevOps & MLOps"]
        GHA["GitHub Actions<br/>CI/CD Pipeline"]
        MLF["MLflow<br/>Model Registry"]
        AIR["Airflow<br/>DAG scheduler"]
        EVD["Evidently AI<br/>Drift detection"]
        ZAP["OWASP ZAP<br/>Security scan"]
        SF2["Salesforce CRM<br/>Apex REST API"]
    end

    subgraph COLLAB["Collaboration & Suivi"]
        GH2["GitHub<br/>Code + PR + Projects"]
        MRM["Mermaid<br/>Diagrammes"]
    end
```

### Matériel

| Composant | Spécification |
|-----------|--------------|
| **Machine** | MacBook Pro (Apple Silicon M-series) |
| **RAM** | 16 GB minimum (Mistral 7B = 4.1 GB + stack Docker) |
| **Stockage** | 50 GB libres (images Docker + modèles Ollama) |
| **OS** | macOS + Docker Desktop |
| **Réseau** | Internet (téléchargement modèles, CDN Swagger en build) |

---

## 11. Processus Git & CI/CD

### Stratégie de Branches

```mermaid
gitGraph
    commit id: "Initial commit"

    branch sprint/1-foundation-architecture
    checkout sprint/1-foundation-architecture
    commit id: "feat: docker compose 6 services"
    commit id: "feat: JWT auth + RBAC"
    commit id: "feat: RGPD schema AES-256"
    commit id: "fix: swagger local assets"
    commit id: "fix: copilot review"
    checkout main
    merge sprint/1-foundation-architecture id: "PR #1 Sprint 1 ✅"

    branch sprint/2-rgpd-consent
    checkout sprint/2-rgpd-consent
    commit id: "feat: granular consent endpoint"
    commit id: "feat: RGPD data export"
    commit id: "feat: right to erasure"
    checkout main
    merge sprint/2-rgpd-consent id: "PR #2 Sprint 2"

    branch sprint/3-rag-llm
    checkout sprint/3-rag-llm
    commit id: "feat: qdrant indexing 84k chunks"
    commit id: "feat: RAG pipeline + Mistral"
    checkout main
    merge sprint/3-rag-llm id: "PR #3 Sprint 3"
```

### Règles Git

| Règle | Description |
|-------|-------------|
| **1 branche par sprint** | `sprint/N-nom-sprint` — jamais de commit direct sur `main` |
| **1 PR par sprint** | Merge via Pull Request avec review Copilot AI |
| **Convention commits** | `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:` |
| **Secrets** | Jamais dans le code — toujours dans `.env` (gitignored) |
| **Tags** | `v1.0.0-sprint1`, `v2.0.0-sprint2`, ... à chaque merge |

### Pipeline CI/CD (Sprint 6)

```mermaid
flowchart LR
    subgraph TRIGGER["Déclencheur"]
        PR["Pull Request<br/>vers main"]
        PUSH["Push sur<br/>branch sprint/*"]
    end

    subgraph CI["Intégration Continue"]
        LINT["Ruff Lint<br/>+ mypy type check"]
        TEST["pytest<br/>--cov ≥ 80%"]
        BUILD["docker build<br/>--no-cache"]
        SEC["OWASP ZAP<br/>Security scan"]
    end

    subgraph CD["Déploiement Continu"]
        TAG["Git tag<br/>v{sprint}.0.0"]
        PUSH_IMG["Push image<br/>GitHub Container Registry"]
        DEPLOY["docker compose up<br/>(environnement staging)"]
    end

    TRIGGER --> LINT
    LINT -->|Succès| TEST
    TEST -->|Succès| BUILD
    BUILD -->|Succès| SEC
    SEC -->|Succès| TAG
    TAG --> PUSH_IMG --> DEPLOY

    LINT & TEST & BUILD & SEC -->|Échec| NOTIFY["❌ Notification<br/>PR bloquée"]
```

---

## Récapitulatif Méthodologique

```mermaid
flowchart LR
    subgraph WHY["Pourquoi cette méthode ?"]
        A1["8 domaines techniques<br/>hétérogènes"]
        A2["Performances ML<br/>connues après expérim."]
        A3["Feedback encadrant<br/>indispensable"]
        A4["Livraisons<br/>incrémentielles"]
    end

    subgraph HOW["Comment ?"]
        B1["Scrum<br/>2 semaines/sprint"]
        B2["52 User Stories<br/>329 Story Points"]
        B3["Git branch/sprint<br/>+ PR + CI/CD"]
        B4["DoD stricte<br/>pytest ≥ 80%"]
    end

    subgraph WHAT["Résultat attendu"]
        C1["10 sprints livrés<br/>août 2026"]
        C2["Plateforme IA<br/>production-ready"]
        C3["Rapport PFE<br/>complet"]
        C4["Soutenance<br/>EMSI Marrakech"]
    end

    WHY --> HOW --> WHAT
```

---

## 12. Plan d'Implémentation — Objectif 10/10

Cette section transforme la roadmap qualité en **plan d'exécution concret** pour atteindre un niveau jury maximal (stabilité technique + preuves mesurables + démonstration reproductible).

### 12.1 Axes de mise en œuvre

| Axe | Action d'implémentation | Critère de réussite |
|-----|--------------------------|---------------------|
| **1. Branche de référence** | Créer `release/jury`, merger `main` + branche sprint active, geler les merges directs | Une seule branche source de vérité |
| **2. CI unifiée** | Pipeline unique lint + tests + build + smoke ingestion | 100% checks verts sur PR |
| **3. Qualité tests** | Corriger les tests instables, couvrir auth/safety/RAG/MCP/ingestion | Suite stable et reproductible |
| **4. Tuning hybride retriever** | Fusion pondérée Dense/BM25 + grid search alpha/k sur benchmark | MRR/NDCG/Recall@k améliorés et tracés |
| **5. Safety clinique** | Jeu red-team (urgences, dosage, injections prompt) + assertions automatiques | Taux de blocage/sécurité mesuré |
| **6. Performance** | Mesurer p95 retrieval, p95 first-token SSE, p95 réponse finale | SLA documentés et respectés |
| **7. Gouvernance données** | Manifeste corpus (source, licence, date, checksum) + procédure refresh | Traçabilité complète des données |
| **8. Observabilité** | Logs structurés pipeline + métriques + dashboard synthèse | Diagnostic incident en quelques minutes |
| **9. Documentation jury** | Consolidation architecture + choix + limites + résultats avant/après | Dossier défendable en soutenance |
| **10. Démo scriptée** | Scénarios fixes FR/Darija/urgence/prix/fallback | Démo stable sans improvisation |

### 12.2 Ordre d'exécution recommandé

```mermaid
flowchart LR
    A["1) Branche release/jury"] --> B["2) CI unifiée"]
    B --> C["3) Stabilisation tests"]
    C --> D["4) Tuning Dense/BM25"]
    D --> E["5) Safety red-team"]
    E --> F["6) Benchmark performance"]
    F --> G["7) Gouvernance corpus"]
    G --> H["8) Observabilité"]
    H --> I["9) Documentation jury"]
    I --> J["10) Démo finale scriptée"]
```

### 12.3 Livrables attendus (preuves)

| Domaine | Livrable concret |
|---------|------------------|
| Git | Branche `release/jury` propre + historique lisible |
| CI/CD | Workflow GitHub Actions vert sur PR et push |
| Tests | Rapport tests + couverture + scénarios critiques |
| Retrieval | Rapport tuning (alpha/k) avec métriques comparatives |
| Sécurité | Rapport red-team + comportements de blocage validés |
| Performance | Tableau p95 par étape du pipeline |
| Données | `corpus_manifest` versionné (provenance/licence/checksum) |
| Ops | Dashboard métriques + logs structurés exploitables |
| Jury | README/Docs harmonisés avec résultats finals |
| Démo | Script opératoire de soutenance (pas à pas) |

### 12.4 Definition of Done global (objectif 10/10)

Le projet est considéré **10/10 prêt soutenance** si :

1. CI verte en continu sur la branche de référence.
2. Tests critiques stables (aucun échec intermittent).
3. Retriever hybride réglé sur benchmark avec gains mesurés.
4. Safety clinique validée par red-team scénarisé.
5. Performance p95 documentée et conforme aux objectifs.
6. Données traçables (source/licence/date/checksum) et reproductibles.
7. Documentation finale cohérente avec l'état réel du code.
8. Démo scriptée exécutable de bout en bout.
