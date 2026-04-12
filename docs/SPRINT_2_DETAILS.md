# Sprint 2 — RGPD & Consentement : Détail Complet
**13 Avr – 26 Avr 2026 | Statut : ✅ TERMINÉ**

> Ce document explique **ce qui a été construit**, **pourquoi chaque décision a été prise**, et **ce sur quoi tu dois te concentrer** en tant que profil Data Science & IA pour maîtriser les fondations RGPD qui gouverneront chacun de tes pipelines IA.

---

## Table des Matières

1. [Vue d'ensemble du Sprint 2](#1-vue-densemble-du-sprint-2)
2. [US-06 — Consentement Granulaire](#2-us-06--consentement-granulaire-patch-patientsuuidconsent)
3. [US-07 — Export de Données RGPD](#3-us-07--export-de-données-rgpd-get-patientsuuiddataexport)
4. [US-08 — Droit à l'Effacement](#4-us-08--droit-à-leffacement-delete-patientsuuid)
5. [US-46 — Journal d'Audit](#5-us-46--journal-daudit-get-adminaudit-logs)
6. [Infrastructure technique](#6-infrastructure-technique)
7. [Bugs résolus & leçons apprises](#7-bugs-résolus--leçons-apprises)
8. [Ce sur quoi tu dois te concentrer — Profil DS/IA](#8-ce-sur-quoi-tu-dois-te-concentrer--profil-dsia)

---

## 1. Vue d'ensemble du Sprint 2

### Objectif
Implémenter les **obligations légales RGPD** qui encadrent l'utilisation des données patients. C'est le sprint qui donne leur sens juridique et éthique à tous les pipelines IA du projet : aucun modèle ML ne peut traiter une donnée sans le consentement explicite du patient.

### Articles RGPD couverts

| Article | Titre | US implémentée |
|---------|-------|----------------|
| Art. 7 | Conditions du consentement | US-06 |
| Art. 17 | Droit à l'effacement | US-08 |
| Art. 20 | Droit à la portabilité des données | US-07 |
| Art. 30 | Registre des activités de traitement | US-46 |

### Ce qui a été livré

```
backend/app/
├── db/models/
│   └── audit_log.py        ← ORM : AuditLog + ConsentLog (tables immuables)
├── core/
│   └── audit.py            ← helpers log_audit() + log_consent()
├── schemas/
│   ├── patient.py          ← ConsentUpdate, PatientDataExport, ErasureResponse
│   └── admin.py            ← AuditLogEntry, AuditLogList (paginée)
├── api/v1/endpoints/
│   ├── patients.py         ← US-06, US-07, US-08
│   └── admin.py            ← US-46
└── api/v1/router.py        ← +2 routers enregistrés

alembic/versions/
└── 20260413_000000_sprint2_orm_models.py   ← migration no-op s2_models_0002

tests/
├── conftest.py             ← refactorisé (sync schema setup + async per-test)
├── test_patients.py        ← 15 tests US-06/07/08
├── test_admin.py           ← 9 tests US-46
└── pytest.ini              ← asyncio_mode=auto, loop_scope=function
```

### KPIs atteints

| Métrique | Cible | Résultat |
|----------|-------|----------|
| Tests Sprint 2 | ≥ 15 | 27 nouveaux tests |
| Tests total | 36 | ✅ 36/36 passent |
| Couverture consentement | 3 types × granted/revoked | ✅ logué par changement |
| Piste d'audit | Toute opération patient | ✅ chaque endpoint loggue |
| Effacement RGPD Art.17 | Identité + anonymisation ML | ✅ 2 étapes |

---

## 2. US-06 — Consentement Granulaire (`PATCH /patients/{uuid}/consent`)

### Ce qui a été fait

Un patient a 3 types de consentement indépendants :

| Champ | Ce qu'il autorise | Utilisé dans |
|-------|-------------------|--------------|
| `consent_iot` | Traitement des données biométriques (IoT) | LSTM anomalie détection (Sprint 7) |
| `consent_nlp` | Traitement du langage (chatbot, résumés) | RAG Mistral (Sprint 3) |
| `consent_sharing` | Partage inter-services (Salesforce CRM) | Sync CRM (Sprint 6) |

### Anatomie d'un appel PATCH consent

```bash
curl -k -X PATCH https://localhost/api/v1/patients/{uuid}/consent \
  -H "Authorization: Bearer <doctor_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "consent_iot": true,
    "consent_nlp": true,
    "consent_sharing": false,
    "channel": "web",
    "cgu_version": "1.0"
  }'
```

Réponse :
```json
{
  "patient_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "consent_iot": true,
  "consent_nlp": true,
  "consent_sharing": false,
  "updated_at": "2026-04-15T10:30:00Z"
}
```

### Logique clé — ne logger que les changements réels

```python
# patients.py — extrait de update_consent()

consent_fields = {
    "iot":     (patient.consent_iot,     body.consent_iot),
    "nlp":     (patient.consent_nlp,     body.consent_nlp),
    "sharing": (patient.consent_sharing, body.consent_sharing),
}

for consent_type, (old_val, new_val) in consent_fields.items():
    if new_val is None:
        continue   # champ absent dans la requête → ignorer
    if new_val == old_val:
        continue   # même valeur → PAS de log (évite pollution piste d'audit)

    action = "granted" if new_val else "revoked"
    await log_consent(db, patient_uuid, consent_type, action, ...)
    setattr(patient, f"consent_{consent_type}", new_val)
```

**Pourquoi vérifier si la valeur a changé ?**

Imagine un médecin qui envoie `consent_iot=True` alors que c'est déjà `True`. Sans cette vérification, on créerait un faux log "granted" qui dirait au patient "ton médecin a re-accordé le consentement IoT le 15/04" — informatiquement faux, légalement confus. RGPD exige une piste d'audit fidèle à la réalité.

### Schéma Pydantic — validation stricte du channel

```python
# schemas/patient.py
class ConsentUpdate(BaseModel):
    consent_iot:     Optional[bool] = None   # None = "ne pas toucher ce flag"
    consent_nlp:     Optional[bool] = None
    consent_sharing: Optional[bool] = None
    channel: str = "web"
    cgu_version: Optional[str] = None

    @field_validator("channel")
    @classmethod
    def channel_must_be_valid(cls, v: str) -> str:
        allowed = {"app", "web", "paper"}
        if v not in allowed:
            raise ValueError(f"channel must be one of {allowed}")
        return v
```

`channel` est crucial pour l'accountability RGPD : il faut savoir si le consentement a été collecté via l'app, le site web, ou un formulaire papier. Un `channel` invalide retourne `422 Unprocessable Entity` **avant** d'atteindre la base de données.

### Résultat dans public.consent_logs (immuable)

```sql
SELECT * FROM public.consent_logs WHERE patient_uuid = '550e8400-...';

 id | patient_uuid | consent_type | action  | channel | cgu_version | ip_address
----+--------------+--------------+---------+---------+-------------+-----------
  1 | 550e8400-... | iot          | granted | web     | 1.0         | 172.18.0.1
  2 | 550e8400-... | nlp          | granted | web     | 1.0         | 172.18.0.1
```

Ces lignes sont **immuables** — les règles PostgreSQL `consent_no_update` et `consent_no_delete` empêchent toute modification, même pour l'admin.

---

## 3. US-07 — Export de Données RGPD (`GET /patients/{uuid}/data/export`)

### Ce qui a été fait

RGPD Art. 20 — chaque patient a le droit d'obtenir une copie structurée de toutes ses données. L'endpoint retourne un JSON complet :

```json
{
  "exported_at": "2026-04-15T11:00:00Z",
  "patient": {
    "patient_uuid": "550e8400-...",
    "consent_iot": true,
    "consent_nlp": true,
    "consent_sharing": false,
    "birth_year": 1985,
    "sex": "M",
    "city_code": "40000",
    "chronic_conditions": ["hypertension", "diabète type 2"],
    "is_active": true,
    "created_at": "2026-04-01T09:00:00Z",
    "updated_at": "2026-04-15T10:30:00Z"
  },
  "consent_history": [
    {"consent_type": "iot", "action": "granted", "channel": "web", "cgu_version": "1.0", "created_at": "..."},
    {"consent_type": "nlp", "action": "granted", "channel": "web", "cgu_version": "1.0", "created_at": "..."}
  ],
  "access_log": [
    {"action": "CONSENT", "resource_type": "patient", "actor_role": "doctor", "created_at": "..."},
    {"action": "EXPORT",  "resource_type": "patient", "actor_role": "admin",  "created_at": "..."}
  ]
}
```

### Ce qui N'est PAS dans l'export

```
❌ full_name_enc   → dans secure.patients_identity (chiffré AES-256)
❌ phone_enc       → idem
❌ email_enc       → idem
```

L'identité civile **ne peut pas être déchiffrée sans la PGCRYPTO_KEY**. Un endpoint DPO dédié (Sprint 5) la déchiffrera avec la clé d'environnement. C'est le principe de **séparation des accès** : l'export Art.20 prouve les données traitées ; le DPO seul peut identifier la personne.

### L'export loggue lui-même son exécution

```python
# patients.py — dans export_patient_data()

# ... requêtes consent_logs et audit_logs ...

# L'export EST une opération sensible → on la logue
await log_audit(
    db=db,
    actor=current_user,
    request=request,
    action="EXPORT",
    resource_type="patient",
    resource_uuid=patient_uuid,
)
```

Résultat : si le patient demande "qui a exporté mes données ?", il apparaît dans le `access_log` de son propre export. **L'audit est réflexif**.

### Pourquoi admin-only et pas doctor ?

- L'export Art.20 est une opération **exceptionnelle** (requête légale du patient)
- Un médecin en consultation n'a pas besoin d'exporter toutes les données — il lit les informations une par une via les endpoints normaux
- Seul l'admin (ou le DPO désigné) traite les demandes RGPD formelles
- Donner l'accès export à tous les médecins = risque de fuite massive si credential compromis

---

## 4. US-08 — Droit à l'Effacement (`DELETE /patients/{uuid}`)

### RGPD Art. 17 — ce que la loi exige

Le patient a le droit d'exiger la suppression de ses données personnelles. Mais dans le contexte médical, des **obligations de conservation légale** s'appliquent (dossiers médicaux = 20 ans en France/Maroc). La solution : **effacement de l'identité + anonymisation des données médicales**.

### Opération en 2 étapes

```python
# patients.py — dans erase_patient()

# Étape 1 — Suppression de l'identité civile (secure schema)
await db.execute(
    delete(PatientIdentity).where(PatientIdentity.patient_uuid == patient_uuid)
)
# Résultat : nom, téléphone, email → DÉFINITIVEMENT supprimés

# Étape 2 — Anonymisation des données ML (public schema)
patient.is_active = False
patient.birth_year = None        # ← feature XGBoost effacée
patient.sex = None               # ← feature XGBoost effacée
patient.city_code = None         # ← feature XGBoost effacée
patient.chronic_conditions = None  # ← feature XGBoost effacée
patient.consent_iot = False
patient.consent_nlp = False
patient.consent_sharing = False
# Résultat : aucune donnée personnelle dans la ligne restante
```

### Pourquoi ne pas supprimer la ligne `public.patients` ?

```sql
-- Relations qui seraient cassées par un DELETE :
public.appointments.patient_uuid  → REFERENCES patients(patient_uuid)
public.consent_logs.patient_uuid  → REFERENCES patients(patient_uuid)
public.audit_logs.resource_uuid   → référence logique (pas de FK) vers patients
```

Si on supprimait la ligne :
1. **ON DELETE CASCADE** efface les rendez-vous historiques — illégal (obligation conservation)
2. Les logs d'audit deviendraient orphelins — la piste légale se casse
3. La migration `ON DELETE RESTRICT` bloquerait la suppression de toute façon

**Solution :** garder le UUID comme "coquille vide" (is_active=False, toutes les données effacées). L'UUID existe mais ne contient plus rien de personnel.

### Idempotence — protection contre le double-effacement

```python
if not patient.is_active:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Patient has already been erased",
    )
```

Si quelqu'un tente d'effacer deux fois → `409 Conflict` au lieu de `200` suivi d'un effacement d'un patient différent par erreur.

### Réponse

```json
{
  "patient_uuid": "550e8400-...",
  "erased_at": "2026-04-15T14:00:00Z",
  "message": "Patient data erased. Civil identity deleted from secure storage. Pseudonymized record anonymized. UUID retained for audit trail integrity."
}
```

---

## 5. US-46 — Journal d'Audit (`GET /admin/audit-logs`)

### Ce qui a été fait

L'endpoint DPO pour consulter la piste d'audit RGPD Art.30. Paginated, filtrable sur 6 dimensions.

### Paramètres de filtrage

```
GET /api/v1/admin/audit-logs
  ?actor_uuid=...     ← "Que fait ce médecin ?"
  &resource_uuid=...  ← "Qui a accédé au patient X ?"
  &action=EXPORT      ← "Tous les exports de données"
  &actor_role=doctor  ← "Actions de tous les médecins"
  &from_date=2026-04-01T00:00:00
  &to_date=2026-04-30T23:59:59
  &limit=50           ← max 200
  &offset=0
```

### Structure de la réponse paginée

```json
{
  "total": 247,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": 247,
      "actor_uuid": "uuid-du-medecin",
      "actor_role": "doctor",
      "action": "CONSENT",
      "resource_type": "patient",
      "resource_uuid": "uuid-du-patient",
      "ip_address": "172.18.0.1",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2026-04-15T10:30:00Z"
    },
    ...
  ]
}
```

### Double requête COUNT + SELECT

```python
# admin.py — deux requêtes nécessaires pour pagination

# Query 1 — compte total (pour que le frontend sache combien de pages)
count_query = select(func.count()).select_from(AuditLog)
if conditions:
    count_query = count_query.where(*conditions)
total = (await db.execute(count_query)).scalar_one()

# Query 2 — données de la page, du plus récent au plus ancien
data_query = (
    select(AuditLog)
    .order_by(AuditLog.created_at.desc())
    .offset(offset)
    .limit(limit)
)
if conditions:
    data_query = data_query.where(*conditions)
```

**Pourquoi 2 requêtes ?** Un seul `SELECT ... LIMIT 50` ne retourne que 50 lignes — impossible de savoir si c'est la dernière page ou s'il en reste 5000. Le `COUNT(*)` donne le total, et le frontend calcule `total_pages = ceil(total / limit)`.

### Vocabulaire des actions (convention interne)

| Action | Signification |
|--------|---------------|
| `READ` | Lecture de données patient |
| `WRITE` | Création ou modification |
| `DELETE` | Effacement (Art.17) |
| `EXPORT` | Export portabilité (Art.20) |
| `CONSENT` | Mise à jour consentement (Art.7) |
| `LOGIN` | Authentification (prévu Sprint 3) |

---

## 6. Infrastructure Technique

### ORM models — `audit_log.py`

```python
# db/models/audit_log.py

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(50))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_uuid: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
```

**Pourquoi `BigInteger` et pas `UUID` pour la PK ?**
Ces tables sont append-only et requêtées par plage de dates (`WHERE created_at BETWEEN ...`). Une PK `BIGSERIAL` séquentielle donne une meilleure localité d'index B-Tree pour les range scans. Une PK UUID aléatoire générerait des pages d'index fragmentées.

### Helper `audit.py` — centralisation

```python
# core/audit.py

async def log_audit(
    db: AsyncSession,
    actor: TokenPayload,
    request: Request,
    action: str,
    resource_type: str,
    resource_uuid: uuid.UUID | str | None = None,
) -> None:
    """
    Ajoute une entrée dans public.audit_logs.
    NE flush PAS, NE commit PAS — s'exécute dans la même transaction
    que l'opération métier. Si l'opération roll-back, le log aussi.
    """
    entry = AuditLog(
        actor_uuid=uuid.UUID(actor.sub),
        actor_role=actor.role,
        action=action,
        resource_type=resource_type,
        resource_uuid=resource_uuid,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )
    db.add(entry)
```

**Atomicité intentionnelle :** `log_audit` s'exécute dans la même transaction SQLAlchemy que l'opération métier. Si la mise à jour du patient échoue et roll-back, le log d'audit roll-back aussi. On n'a jamais un log qui dit "le consentement a été modifié" alors que la modification a en réalité échoué.

**Extraction de l'IP derrière Nginx :**
```python
def _get_client_ip(request: Request) -> str | None:
    # Nginx ajoute X-Real-IP (configuré dans nginx.conf)
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip
    return request.client.host if request.client else None
```

Sans `X-Real-IP`, tous les logs afficheraient l'IP de Nginx (`172.18.0.x`) au lieu de l'IP du client réel.

### Migration Alembic — no-op intentionnelle

```python
# 20260413_000000_sprint2_orm_models.py

revision: str = 's2_models_0002'
down_revision: Union[str, None] = 's1_baseline_0001'

def upgrade() -> None:
    pass   # tables déjà créées par init_db.sql

def downgrade() -> None:
    pass   # on ne supprime jamais les tables d'audit
```

**Pourquoi pas `CREATE TABLE` ici ?** Les tables `audit_logs` et `consent_logs` existent déjà depuis `scripts/init_db.sql` (Sprint 1). Alembic n'en savait pas encore rien — c'est cette migration qui enregistre ces tables dans la chaîne de révisions. Les futures migrations (Sprint 3+) pourront y faire référence via `autogenerate`.

---

## 7. Bugs résolus & Leçons Apprises

### Bugs applicatifs

| # | Bug | Cause | Fix |
|---|-----|-------|-----|
| 1 | `log_audit` enregistre l'IP Nginx (`172.18.x`) | `request.client.host` = IP du reverse proxy | Lire `X-Real-IP` en priorité (header ajouté par nginx.conf) |
| 2 | `PATCH consent` loggue un "granted" même si la valeur est déjà `True` | Pas de comparaison old/new avant d'écrire le ConsentLog | Ajouter `if new_val == old_val: continue` avant le log |
| 3 | `DELETE patient` retourne 200 si le patient est déjà effacé | Pas de guard sur `is_active=False` | Ajouter `if not patient.is_active: raise HTTPException(409)` |

### Infrastructure de tests — problème complexe résolu

Le refactoring de `conftest.py` a nécessité 4 tentatives pour résoudre un problème subtil de **compatibilité event loop Python / asyncpg / pytest-asyncio**.

#### Tentative 1 — Session-scoped engine + function-scoped session
```python
# conftest.py — ÉCHOUE
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(...)
    yield engine           # ← crée des connexions asyncpg sur loop A

@pytest_asyncio.fixture   # function-scoped
async def test_db(test_engine):
    factory = async_sessionmaker(test_engine, ...)
    async with factory() as session:  # ← tente d'utiliser l'engine sur loop B
        yield session
```

**Erreur :** `RuntimeError: Future attached to a different loop`

**Cause :** asyncpg lie chaque connexion à l'event loop qui l'a créée. `test_engine` (session-scoped) crée ses connexions sur la loop de session ; `test_db` (function-scoped) tourne sur une loop par-test → incompatibilité.

---

#### Tentative 2 — asyncio_default_fixture_loop_scope = session
```ini
# pytest.ini — ÉCHOUE
asyncio_default_fixture_loop_scope = session
```

**Erreur :** les tests passaient, mais certains échouaient avec `RuntimeError: Task X got Future ... attached to a different loop` où X était un test **différent** de celui qui tournait.

**Cause :** avec `loop_scope = session`, pytest-asyncio **schedule TOUS les tests comme des tâches concurrentes** sur la loop de session. Quand un test `await`e quelque chose, asyncio peut switcher vers un autre test — les deux essayant d'utiliser la même connexion asyncpg simultanément. C'est du **cooperative multitasking involontaire**.

---

#### Tentative 3 — db_schema async session-scoped + loop_scope = function
```python
@pytest_asyncio.fixture(scope="session")  # async + session-scoped
async def db_schema():
    ...
```
```ini
asyncio_default_fixture_loop_scope = function
```

**Erreur :** `ScopeMismatch: You tried to access the function scoped fixture event_loop with a session scoped request object`

**Cause :** pytest-asyncio 0.24 avec `loop_scope = function` fait de `event_loop` une fixture function-scoped. Une fixture async session-scoped essaie d'utiliser cette `event_loop` function-scoped → conflit de scope impossible à résoudre.

---

#### ✅ Solution finale — schema sync + sessions async par test
```python
# conftest.py — FONCTIONNE

@pytest.fixture(scope="session")   # ← SYNC, pas async
def db_schema():
    """Utilise psycopg2 (sync) — aucun event loop impliqué."""
    engine = create_engine(TEST_DATABASE_URL_SYNC)   # ← psycopg2
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS secure"))
    Base.metadata.create_all(engine)
    engine.dispose()
    yield
    # teardown...

@pytest_asyncio.fixture   # ← ASYNC, function-scoped
async def test_db(db_schema):
    """Nouvel engine asyncpg par test — connexions dans la loop du test."""
    engine = create_async_engine(TEST_DATABASE_URL)   # ← asyncpg
    factory = async_sessionmaker(engine, ...)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
```

**Principe :** séparer les responsabilités par nature (sync vs async) :
- Setup du schéma = opération one-shot → sync, pas de loop, session-scoped ✅
- Connexions DB des tests = par test → async, loop propre, function-scoped ✅
- Aucun partage de connexion entre loops ✅

**Leçon :** asyncpg et les event loops Python sont stricts. La règle d'or : **une connexion asyncpg ne peut être utilisée que dans la loop qui l'a créée**. Tout partage de connexion entre loops = crash.

---

## 8. Ce sur quoi tu dois te concentrer — Profil DS/IA

> Sprint 2 est le sprint RGPD. Tu pourrais penser que c'est du "backend pur" et que ça ne te concerne pas directement. **C'est faux.** Chaque pipeline IA que tu vas écrire à partir du Sprint 3 sera bloqué ou autorisé par ce que tu as construit ici.

---

### 🔴 CRITIQUE — Le consentement gate ton IA

#### Le pattern que tu vas écrire dans CHAQUE endpoint IA

```python
# Sprint 3 — endpoint chat RAG
@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_role("patient")),
):
    # Charger le patient
    result = await db.execute(
        select(Patient).where(Patient.patient_uuid == current_user.sub)
    )
    patient = result.scalar_one_or_none()

    # ← SPRINT 2 : vérifier le consentement NLP avant d'appeler Mistral
    if not patient.consent_nlp:
        raise HTTPException(
            status_code=403,
            detail="Consentement NLP requis pour utiliser l'assistant IA"
        )

    # Seulement ici : appel RAG → Qdrant → Mistral
    response = await rag_pipeline.query(body.message, patient.patient_uuid)
    ...
```

```python
# Sprint 7 — endpoint LSTM IoT
@router.post("/biometrics/analyze")
async def analyze_biometrics(
    body: BiometricsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_any_staff),
):
    patient = await load_patient(db, body.patient_uuid)

    # ← SPRINT 2 : consentement IoT gate le LSTM
    if not patient.consent_iot:
        raise HTTPException(
            status_code=403,
            detail="Consentement IoT requis pour l'analyse biométrique"
        )

    # Seulement ici : inférence LSTM
    anomalies = await lstm_model.predict(body.biometrics)
    ...
```

**Résumé du pattern :**
```
1. charger le patient  →  2. vérifier consent_X  →  3. appeler le modèle IA
```
**Ne jamais sauter l'étape 2.** C'est une obligation légale, pas une option.

---

#### Table de correspondance consentement → pipeline IA

| Si `consent_...` est `True` | Pipeline IA débloqué | Sprint |
|---|---|---|
| `consent_nlp` | RAG (Qdrant + Mistral) | 3 |
| `consent_nlp` | Chatbot symptômes | 3 |
| `consent_iot` | LSTM anomalie détection | 7 |
| `consent_iot` | Analyse biométrique temps-réel | 7 |
| `consent_sharing` | Sync Salesforce CRM | 6 |
| `consent_sharing` | Export inter-cliniques | 6 |

Si un patient révoque `consent_nlp`, ton pipeline RAG doit retourner `403`, pas appeler Mistral. Ce n'est pas un bug — c'est le comportement attendu.

---

### 🔴 CRITIQUE — Comprendre `log_audit()` pour ne pas oublier de l'appeler

Chaque fois que tu crées un endpoint qui **lit ou écrit des données patient**, tu dois logguer. Sinon le registre RGPD Art.30 est incomplet.

```python
# Pattern à répéter dans tous tes futurs endpoints

@router.post("/rag/query")
async def rag_query(
    body: RagRequest,
    request: Request,                    # ← nécessaire pour log_audit
    db: AsyncSession = Depends(get_db),
    current_user: TokenPayload = Depends(require_any_staff),
):
    # ... logique RAG ...

    # OBLIGATOIRE : loguer l'accès
    await log_audit(
        db=db,
        actor=current_user,
        request=request,
        action="READ",
        resource_type="patient",
        resource_uuid=body.patient_uuid,
    )

    return result
```

La fonction `log_audit()` est dans `app.core.audit`. Elle prend **moins de 5 secondes à ajouter** à un endpoint. Ne pas l'oublier = violation RGPD Art.30.

---

### 🟠 IMPORTANT — Comprendre la philosophie, pas les détails

#### L'atomicité des logs avec les opérations métier

```python
# Mauvais pattern (à éviter) :
async def update_consent(patient_uuid, body, db):
    patient.consent_iot = True
    await db.commit()                    # commit l'opération métier
    await log_audit(...)                 # log APRÈS commit
    await db.commit()                   # 2ème commit pour le log
    # Si le 2ème commit échoue → opération loggée mais log absent

# Bon pattern (Sprint 2) :
async def update_consent(patient_uuid, body, db):
    patient.consent_iot = True
    await log_audit(db, ...)             # db.add() seulement, pas de commit
    # get_db() commitera les deux en une seule transaction
    # Si ça échoue → rollback les deux ensemble
```

L'audit et l'opération métier partagent la même transaction SQLAlchemy. C'est `get_db()` (Sprint 1) qui committe tout à la fin. Tu n'as pas besoin de committer manuellement dans tes endpoints.

#### La pagination — pattern standard

```python
# Pattern que tu vas réutiliser dans Sprint 5 (résultats ML) et Sprint 7 (alertes IoT)

# Toujours retourner : total + limit + offset + items
class ResultList(BaseModel):
    total: int     # ← pour calculer le nombre de pages côté frontend
    limit: int
    offset: int
    items: List[ResultItem]

# Toujours 2 requêtes : COUNT + SELECT avec LIMIT/OFFSET
total = (await db.execute(select(func.count()).select_from(MyModel))).scalar_one()
items = (await db.execute(select(MyModel).offset(offset).limit(limit))).scalars().all()
```

Ce pattern apparaît dans US-46 (audit logs), et sera le même pour les alertes IoT, les rendez-vous, les prédictions XGBoost.

---

### 🟢 PEUT ATTENDRE — Détails techniques fins

- Le choix `BigInteger` vs `UUID` pour les PKs d'audit (performance B-Tree)
- Les détails de la migration no-op Alembic (tu la copies, tu ne la réinventes pas)
- La double requête COUNT/SELECT (tu recopies le pattern sans devoir le dériver)
- L'implémentation de `_get_client_ip()` derrière Nginx

---

### Exercice pratique recommandé (45 min)

```bash
# 1. Lancer la stack
docker compose up -d

# 2. Créer un patient manuellement (SQL direct)
docker compose exec postgres psql -U medisense_user -d medisense_db -c "
INSERT INTO public.patients (consent_iot, consent_nlp, consent_sharing, birth_year, sex, city_code)
VALUES (false, false, false, 1990, 'M', '40000')
RETURNING patient_uuid;"
# ← Copier le UUID retourné

# 3. Se connecter en admin
TOKEN=$(curl -sk -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medisense.ai","password":"Admin1234!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 4. Accorder le consentement NLP
curl -sk -X PATCH https://localhost/api/v1/patients/{uuid}/consent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"consent_nlp": true, "channel": "web", "cgu_version": "1.0"}'
# → Vérifier que consent_nlp est true dans la réponse

# 5. Exporter les données du patient
curl -sk https://localhost/api/v1/patients/{uuid}/data/export \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# → Observer les sections : patient, consent_history, access_log
# → consent_history doit avoir 1 entrée (granted nlp)
# → access_log doit avoir 1 entrée (CONSENT) et 1 (EXPORT)

# 6. Consulter l'audit log complet
curl -sk "https://localhost/api/v1/admin/audit-logs?resource_uuid={uuid}" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# → Toutes les opérations sur ce patient dans l'ordre chronologique

# 7. Essayer de révoquer le consentement NLP
curl -sk -X PATCH https://localhost/api/v1/patients/{uuid}/consent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"consent_nlp": false, "channel": "web"}'
# → Re-exporter : consent_history a maintenant 2 entrées (granted, revoked)
```

---

### Questions à être capable de répondre

1. Pourquoi `consent_iot=True` envoyé alors que `consent_iot` est déjà `True` ne crée **pas** de ligne dans `consent_logs` ?

2. Après un effacement (DELETE /patients/{uuid}), la ligne dans `public.patients` existe toujours avec `is_active=False`. Est-ce une faille RGPD ou un comportement voulu ?

3. Si un endpoint crée une entrée dans `audit_logs` mais que la DB roll-back ensuite (erreur serveur), est-ce que le log d'audit est quand même écrit ?

4. Pourquoi le chatbot RAG (Sprint 3) doit vérifier `consent_nlp` **avant** d'envoyer une requête à Qdrant, plutôt qu'après avoir récupéré les résultats ?

5. Un médecin peut-il accéder à `GET /admin/audit-logs` ? Pourquoi ?

---

### Ce que Sprint 2 débloque pour ton profil DS/IA

```
Sprint 2 (fait)
     │
     ├─ consent_nlp ──────────────────────────→ Sprint 3 : RAG activé/bloqué
     │                                          Sprint 3 : Chatbot activé/bloqué
     │
     ├─ consent_iot ──────────────────────────→ Sprint 7 : LSTM activé/bloqué
     │                                          Sprint 7 : Kafka consumer activé/bloqué
     │
     ├─ consent_sharing ──────────────────────→ Sprint 6 : Sync CRM activé/bloqué
     │
     ├─ log_audit() ──────────────────────────→ Tous les sprints : obligation Art.30
     │
     └─ PatientDataExport ────────────────────→ Sprint 5 : ML features exportées
                                                Sprint 5 : SHAP values incluses dans export
```

**Retiens une chose :** les 3 flags de consentement (`consent_iot`, `consent_nlp`, `consent_sharing`) sont les **interrupteurs maîtres** de toute ton architecture IA. Ils ne sont pas des contraintes imposées de l'extérieur — ils **définissent quelles données tu as légalement le droit d'utiliser dans tes modèles**.

Un modèle ML entraîné sur des données sans consentement n'est pas seulement illégal : il produit des prédictions sur une population que tu n'as pas le droit d'observer. Tes features sont biaisées dès le départ.

---

*Sprint suivant : **Sprint 3 — RAG & Chatbot Médical** (27 Avr – 10 Mai 2026)*
*Premier pipeline IA du projet — Qdrant + Mistral 7B + historique Redis*
