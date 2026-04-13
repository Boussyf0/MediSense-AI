# Sprint 3 — RAG Pipeline & LLM: Plan Technique Complet

**Branche**: `sprint/3-rag-pipeline`
**Dates**: 27 Avr - 10 Mai 2026
**Story Points**: 34 pts (US-09: 8, US-10: 13, US-11: 8, US-12: 5)

---

## 1. Vue d'ensemble de l'architecture

### 1.1 Hybrid MCP-RAG Architecture

MediSense ne fait pas un simple "embed + retrieve + generate". L'architecture combine :

- **Retrieval hybride** : Dense (multilingual-e5) + Sparse (BM25) fusionnee par RRF dans Qdrant
- **MCP Servers** : agents temps reel pour interroger WHO ICD-11 et ANSM (medicaments)
- **Safety Layer** : seuil de confiance, avertissements medicamenteux, verification d'allergies
- **SSE Streaming** : premier token < 200ms (masque la latence Mistral 7B)
- **Darija->FR translation** : traduction cognitive avant retrieval pour maximiser la precision

### 1.2 Flux d'execution complet

```
Patient Input (FR / AR / Darija)
       |
       v
[1] LANGUAGE DETECTION          langdetect + Darija stopwords (<5ms)
       |
       v
[2] QUERY NORMALIZER            Darija/AR -> clinical FR via Mistral 7B
       |
       v (normalized_query_fr)
       |--------------------+----------------------|
       v                    v                      v
[3a] DENSE SEARCH      [3b] BM25 SEARCH     [3c] MCP SERVERS
 multilingual-e5        Qdrant sparse         WHO ICD-11 API
 -> Qdrant HNSW         top-20                ANSM drugs API
 top-20                                       (async, 3s timeout,
       |                    |                  fallback to static)
       +--------+-----------+                      |
                |                                  |
         RRF merge (top-5)                         |
                |<---------------------------------+
                v
[4] ICD-10 ENTITY BOOST         payload filter sur codes medicaux
                |
                v
[5] SAFETY LAYER                confidence < 0.3 -> "consultez un medecin"
                |                drug dosage -> avertissement obligatoire
                v                allergy contradiction check
[6] LLM GENERATION              Mistral 7B via Ollama (SSE streaming)
                |                system prompt + chunks + MCP data + guardrails
                v
[7] PERSIST (async)             PostgreSQL pgcrypto AES-256
```

---

## 2. User Stories - Criteres d'acceptation detailles

### US-09 : Mistral 7B via Ollama (8 pts) - Must Have

**Objectif** : Integrer Mistral 7B comme moteur de generation avec latence P95 < 150ms (first token via SSE)

**Criteres d'acceptation** :
- Mistral 7B demarre via Ollama dans docker-compose
- Endpoint `/api/v1/chat` retourne un flux SSE (Server-Sent Events)
- Time-to-first-token (TTFT) < 200ms mesure en test
- System prompt medical avec guardrails anti-hallucination
- Fallback gracieux si Ollama est down (HTTP 503 + message clair)
- Health check Ollama integre dans le lifespan FastAPI

**Fichiers** :
- `app/rag/llm.py` — client Ollama (generate + streaming)
- `app/api/v1/endpoints/chat.py` — endpoint SSE
- `app/schemas/chat.py` — ChatRequest, ChatChunk, ChatResponse

---

### US-10 : Indexer 84k chunks medicaux dans Qdrant (13 pts) - Must Have

**Objectif** : Construire un corpus medical de ~84k chunks a partir de sources ouvertes et legales

**Sources de donnees** :

| Source | Description | Chunks estimes | Acces |
|--------|-------------|:--------------:|-------|
| WHO ICD-10 | 14 400 codes maladies (FR) | ~18 000 | XML gratuit (who.int) |
| ANSM | Base medicaments francaise (medicaments.gouv.fr) | ~45 000 | Open data CSV |
| HAS | Recommandations cliniques (Haute Autorite de Sante) | ~15 000 | PDF publics |
| PubMed OA | Resumes medicaux (sous-ensemble FR) | ~6 000 | API gratuite |

**Strategie de chunking semantique** (PAS de split fixe 512 tokens) :
- ICD-10 : 1 chunk = 1 code maladie + description complete
- ANSM : 1 chunk = 1 medicament (nom + indications + contre-indications + posologie)
- HAS : 1 chunk = 1 section de recommandation (split sur headings, max 800 tokens)
- PubMed : 1 chunk = 1 abstract complet

**Schema payload Qdrant** :
```json
{
  "source": "ansm | icd10 | has | pubmed",
  "type": "drug | disease | guideline | abstract",
  "name": "Ibuprofene",
  "icd10_codes": ["M79.3", "R50"],
  "language": "fr",
  "section": "posologie_pediatrique",
  "text": "Enfants de plus de 3 mois: 20 a 30 mg/kg/jour..."
}
```

**Qdrant collection config** :
- Collection : `medisense_medical`
- Dense vectors : 768-dim (multilingual-e5-base), distance = Cosine
- Sparse vectors : BM25 (Qdrant built-in), index = text field
- HNSW index : m=16, ef_construct=100
- Payload index sur : `source`, `type`, `icd10_codes`, `language`

**Criteres d'acceptation** :
- Script `ingest_medical_corpus.py` indexe >= 84 000 chunks
- Collection Qdrant operationnelle avec hybrid search (dense + sparse)
- Temps d'indexation < 30 min (batch upsert 100 vectors/requete)
- Chaque chunk a un payload structure complet
- Test de retrieval : requete "douleur thoracique" retourne des chunks cardio en top-5

**Fichiers** :
- `app/rag/embedder.py` — multilingual-e5-base embeddings
- `app/rag/vectorstore.py` — Qdrant client (collection setup, upsert, hybrid search)
- `scripts/ingest_medical_corpus.py` — pipeline d'ingestion
- `data/darija_stopwords.txt` — 200 marqueurs Darija

---

### US-11 : Chatbot symptomes FR/AR/Darija avec triage cognitif (8 pts) - Must Have

**Objectif** : Chatbot multilingue capable de comprendre le Darija marocain et de triager les symptomes

**Flux linguistique** :
1. Patient ecrit en Darija : "rasi kaydrni bzaf w kanchrb doliprane"
2. `language.py` detecte : Darija (langdetect + stopwords)
3. `normalizer.py` traduit en FR medical : "Cephalees intenses, prise de paracetamol"
4. Le retrieval opere en FR (meilleure precision)
5. Le LLM genere la reponse en Darija (instruction dans le system prompt)

**Detection de langue** :
- `langdetect` pour FR vs AR (Modern Standard Arabic)
- Heuristique Darija : script arabe + mots-cles marocains OU script latin + stopwords Darija
- Liste de 200 stopwords Darija : "dyal", "kayn", "machi", "bzzaf", "chhal", "kifach", etc.
- Fallback : FR par defaut

**Triage cognitif** :
Le system prompt inclut une logique de triage :
- Symptomes URGENTS (douleur thoracique, dyspnee, AVC) -> "Appelez le 15 immediatement"
- Symptomes MODERES -> consultation recommandee + informations
- Symptomes LEGERS -> informations + auto-soins

**Criteres d'acceptation** :
- Detection correcte FR/AR/Darija sur 50 phrases de test
- Traduction Darija->FR preservant le sens medical
- Reponse dans la langue detectee du patient
- Triage : "douleur thoracique" -> message d'urgence
- Conversation multi-tour (conversation_id persiste)

**Fichiers** :
- `app/rag/language.py` — detection FR/AR/Darija
- `app/rag/normalizer.py` — traduction vers FR medical via Mistral
- `app/rag/pipeline.py` — orchestrateur complet
- `data/darija_stopwords.txt`

---

### US-12 : Cross-encoder re-ranking sur top-20 chunks (5 pts) - Should Have

**Objectif** : Implementer le re-ranking pour ameliorer la precision du retrieval

**Strategie hybride** (resolution du conflit latence vs precision) :

Le HOT PATH utilise Qdrant RRF (dense + BM25) — rapide (~15ms).
Le cross-encoder `mmarco-mMiniLMv2-L12-H384-v1` est disponible en mode EVALUATION :
- Endpoint `/api/v1/admin/rerank-eval` : compare qualite RRF vs cross-encoder
- Le cross-encoder tourne sur batch offline (pas dans la boucle chat)
- Metriques : MRR@5, NDCG@5, Hit Rate sur un jeu de 100 queries medicales

**Pourquoi ce choix** :
- RRF inline = ~15ms, cross-encoder inline = ~150-200ms (CPU)
- Pour un chatbot temps reel, RRF est suffisant (85-90% de la qualite cross-encoder)
- L'endpoint d'eval prouve que le re-ranking est implemente et mesure (US-12 satisfait)
- En production avec GPU, le cross-encoder pourrait etre active dans le hot path

**Criteres d'acceptation** :
- Cross-encoder `mmarco-mMiniLMv2-L12-H384-v1` charge et fonctionnel
- Endpoint `/admin/rerank-eval` retourne MRR@5 et NDCG@5
- Documentation du delta de qualite RRF vs cross-encoder
- Qdrant hybrid search (dense + BM25 + RRF) operationnel dans le hot path

**Fichiers** :
- `app/rag/reranker.py` — cross-encoder (batch eval mode)
- `app/api/v1/endpoints/admin.py` — ajout endpoint rerank-eval

---

## 3. MCP Servers — Architecture detaillee

### 3.1 Qu'est-ce que MCP ?

Model Context Protocol (MCP) est un protocole standard (Anthropic, 2024) pour connecter
des LLM a des outils externes. Au lieu de tout stocker localement, le LLM "appelle" des
serveurs MCP pour obtenir des donnees en temps reel.

### 3.2 Serveurs MCP MediSense

**ANSM Drug Server** (`app/mcp/ansm_server.py`) :
- Outil : `search_drug(name: str) -> DrugInfo`
- Source : API ANSM (base-donnees-publique.medicaments.gouv.fr)
- Retourne : indications, contre-indications, posologie, effets secondaires
- Timeout : 3s, fallback vers chunks Qdrant si echec

**WHO ICD-11 Server** (`app/mcp/icd11_server.py`) :
- Outil : `search_disease(query: str, lang: str) -> DiseaseInfo`
- Source : API WHO ICD-11 (icd.who.int/icdapi)
- Retourne : code, titre, definition, inclusions, exclusions
- Timeout : 3s, fallback vers chunks Qdrant si echec

### 3.3 Integration dans le pipeline

```python
# Phase 3 : MCP servers en parallele du retrieval Qdrant
async with asyncio.TaskGroup() as tg:
    qdrant_task = tg.create_task(vectorstore.hybrid_search(query_fr))
    mcp_drug    = tg.create_task(mcp_client.search_drug(entities))
    mcp_disease = tg.create_task(mcp_client.search_disease(query_fr))

# Merge: chunks Qdrant + contexte MCP
context = merge_qdrant_and_mcp(qdrant_task.result(), mcp_drug.result(), mcp_disease.result())
```

### 3.4 Circuit Breaker

Si un MCP server echoue :
1. Timeout 3s -> abandon de la requete MCP
2. Le pipeline continue avec les chunks Qdrant seuls
3. Log de l'echec pour monitoring
4. Apres 5 echecs consecutifs -> circuit ouvert (skip MCP pendant 60s)

---

## 4. Safety Layer — Securite medicale

### 4.1 Seuil de confiance

```python
# Apres retrieval, calculer le score moyen des top-3 chunks
avg_score = mean([chunk.score for chunk in top_3])

if avg_score < 0.3:
    return "Je ne dispose pas d'informations fiables. Veuillez consulter votre medecin."
```

### 4.2 Detection de posologie

Si la question mentionne un dosage/posologie :
- Scanner la reponse du LLM pour des patterns numeriques (mg, ml, comprimes)
- Injecter automatiquement : "Les dosages mentionnes sont indicatifs. Respectez la prescription de votre medecin."

### 4.3 Verification d'allergies

Si le patient a un profil avec allergies renseignees (Sprint 2, table patients) :
- Croiser les medicaments mentionnes dans la reponse avec les allergies du patient
- Si contradiction : avertissement explicite

### 4.4 System Prompt medical

```
Tu es MediSense, assistant medical IA. Regles OBLIGATOIRES :
1. Reponds UNIQUEMENT a partir des sources fournies
2. Si les sources ne contiennent pas l'information -> "Je ne dispose pas
   de cette information. Veuillez consulter votre medecin."
3. Ne JAMAIS inventer de posologie ou dosage
4. URGENCE (douleur thoracique, dyspnee, AVC) -> "Appelez le 15 immediatement"
5. Toujours terminer par : "Ceci est une aide informative, non un diagnostic.
   Consultez un professionnel de sante."
6. Cite tes sources : [Source: {nom}, {type}]
```

---

## 5. Modele de donnees

### 5.1 Table `conversations`

```sql
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES secure.patients(id),
    title           TEXT,                        -- auto-generated from first message
    language        VARCHAR(10) DEFAULT 'fr',    -- detected language
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

### 5.2 Table `messages`

```sql
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL,        -- 'user' | 'assistant'
    content_encrypted BYTEA NOT NULL,            -- pgcrypto_sym_encrypt(content, key)
    sources         JSONB,                       -- [{source, type, name, score}]
    confidence      FLOAT,                       -- retrieval confidence score
    tokens_used     INTEGER,                     -- for monitoring
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### 5.3 RGPD Compliance

- `content_encrypted` : AES-256 via `pgp_sym_encrypt(text, key)` — meme pattern que Sprint 2
- Endpoint `DELETE /chat/{conversation_id}` : suppression complete (droit a l'effacement)
- Retention : 90 jours par defaut, configurable
- Audit log : chaque acces au chat est trace dans `audit_logs` (Sprint 2)

---

## 6. Structure des fichiers

```
backend/
├── app/
│   ├── rag/
│   │   ├── __init__.py              # Exports publics
│   │   ├── language.py              # [US-11] langdetect + Darija stopwords
│   │   ├── normalizer.py            # [US-11] Darija/AR -> FR via Mistral
│   │   ├── embedder.py              # [US-10] multilingual-e5-base (768-dim)
│   │   ├── vectorstore.py           # [US-10] Qdrant hybrid: Dense+BM25+RRF
│   │   ├── medical_entities.py      # [US-10] ICD-10 code extraction + payload boost
│   │   ├── reranker.py              # [US-12] mmarco cross-encoder (eval mode)
│   │   ├── safety.py                # [US-11] confidence gate + drug warnings
│   │   ├── llm.py                   # [US-09] Mistral 7B via Ollama (SSE)
│   │   └── pipeline.py              # Orchestrateur complet (steps 1-7)
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── client.py                # MCP client async (circuit breaker)
│   │   ├── ansm_server.py           # ANSM drug lookup tool
│   │   └── icd11_server.py          # WHO ICD-11 disease lookup tool
│   ├── api/v1/endpoints/
│   │   └── chat.py                  # POST /chat (SSE), GET /chat/{id}, DELETE /chat/{id}
│   ├── schemas/
│   │   └── chat.py                  # ChatRequest, ChatChunk, ChatResponse
│   └── db/models/
│       └── conversation.py          # Conversation + Message (pgcrypto)
├── scripts/
│   └── ingest_medical_corpus.py     # [US-10] Indexation 84k chunks
├── data/
│   └── darija_stopwords.txt         # 200 marqueurs Darija
├── alembic/versions/
│   └── 20260427_000000_sprint3_conversations.py
└── tests/
    ├── test_chat.py                 # Tests endpoint chat (SSE, multilingual)
    ├── test_rag_pipeline.py         # Tests unitaires pipeline RAG
    ├── test_language.py             # Tests detection FR/AR/Darija
    ├── test_safety.py               # Tests safety layer
    └── test_mcp.py                  # Tests MCP servers (mocked)
```

---

## 7. Dependances a ajouter

```
# requirements.txt additions
qdrant-client==1.12.1              # vector store client + hybrid search
sentence-transformers==3.3.1       # embeddings (e5-base) + cross-encoder (eval)
langdetect==1.0.9                  # FR/AR language detection
sse-starlette==2.1.3               # Server-Sent Events pour FastAPI
```

---

## 8. Ordre d'implementation

| Etape | Fichiers | Dependances | US |
|:-----:|----------|-------------|:--:|
| 1 | `rag/language.py` + `data/darija_stopwords.txt` + `tests/test_language.py` | Aucune | US-11 |
| 2 | `rag/embedder.py` + `rag/vectorstore.py` | Qdrant running | US-10 |
| 3 | `scripts/ingest_medical_corpus.py` | Etape 2 | US-10 |
| 4 | `rag/normalizer.py` | Ollama running | US-11 |
| 5 | `rag/llm.py` | Ollama running | US-09 |
| 6 | `mcp/client.py` + `mcp/ansm_server.py` + `mcp/icd11_server.py` | httpx | - |
| 7 | `rag/medical_entities.py` + `rag/safety.py` | Etape 2 | US-11 |
| 8 | `rag/pipeline.py` | Etapes 1-7 | All |
| 9 | `db/models/conversation.py` + migration alembic | PostgreSQL | - |
| 10 | `schemas/chat.py` + `api/v1/endpoints/chat.py` | Etapes 8-9 | US-09/11 |
| 11 | `rag/reranker.py` + endpoint admin eval | Etape 2 | US-12 |
| 12 | Tests complets | Tout | All |
| 13 | `docs/SPRINT_3_DETAILS.md` | Tout | - |

---

## 9. Definition of Done (DoD)

- [ ] 4 US (US-09, US-10, US-11, US-12) implementees et testees
- [ ] >= 84 000 chunks indexes dans Qdrant
- [ ] Detection FR/AR/Darija correcte sur 50 phrases de test
- [ ] SSE streaming fonctionnel (premier token < 200ms)
- [ ] Safety layer : seuil confiance + avertissements medicamenteux
- [ ] MCP servers operationnels avec circuit breaker
- [ ] Conversations chiffrees pgcrypto AES-256
- [ ] Endpoint DELETE /chat/{id} (droit a l'effacement RGPD)
- [ ] Couverture tests >= 80%
- [ ] Pas de donnees proprietaires (Vidal, DSM-5) — sources ouvertes uniquement
- [ ] Documentation Sprint 3 Details complete
