# Sprint 1 — Fondation & Authentification : Détail Complet
**30 Mar – 12 Avr 2026 | Statut : ✅ TERMINÉ**

> Ce document explique **ce qui a été construit**, **pourquoi chaque décision a été prise**, et **ce sur quoi tu dois te concentrer** en tant que profil Data Science & IA pour bien appréhender la suite du projet.

---

## Table des Matières

1. [Vue d'ensemble du Sprint 1](#1-vue-densemble-du-sprint-1)
2. [US-01 — Infrastructure Docker](#2-us-01--infrastructure-docker-6-services)
3. [US-02 — Sécurité HTTPS & Headers OWASP](#3-us-02--sécurité-https--headers-owasp)
4. [US-03 — Authentification JWT + Redis](#4-us-03--authentification-jwt--redis)
5. [US-04 — RBAC : Contrôle d'Accès par Rôle](#5-us-04--rbac--contrôle-daccès-par-rôle)
6. [US-05 — Schéma RGPD + AES-256](#6-us-05--schéma-rgpd--aes-256)
7. [US-45 — Swagger UI (assets locaux)](#7-us-45--swagger-ui-assets-locaux)
8. [Bugs résolus & leçons apprises](#8-bugs-résolus--leçons-apprises)
9. [Ce sur quoi tu dois te concentrer — Profil DS/IA](#9-ce-sur-quoi-tu-dois-te-concentrer--profil-dsia)

---

## 1. Vue d'ensemble du Sprint 1

### Objectif
Poser les **fondations irréversibles** du projet. Tout ce qui vient après (RAG, LSTM, XGBoost) repose sur ce sprint. Un bug ici = problèmes en cascade dans tous les sprints suivants.

### Ce qui a été livré

```
MediSense-AI/
├── docker-compose.yml          ← 6 services, healthchecks, volumes nommés
├── nginx/nginx.conf            ← TLS 1.3, rate limiting, reverse proxy
├── scripts/init_db.sql         ← Schéma complet PostgreSQL (6 tables)
├── backend/
│   ├── Dockerfile              ← Multi-stage build, non-root user
│   ├── requirements.txt        ← Toutes dépendances explicites
│   └── app/
│       ├── main.py             ← FastAPI, middleware, Swagger custom
│       ├── core/
│       │   ├── config.py       ← Settings Pydantic depuis .env
│       │   ├── security.py     ← JWT, bcrypt, Redis blacklist, RBAC map
│       │   └── dependencies.py ← get_current_user(), require_role()
│       ├── api/v1/endpoints/
│       │   ├── auth.py         ← /login, /refresh, /logout, /me
│       │   └── health.py       ← /health (Postgres + Redis check)
│       ├── db/
│       │   ├── session.py      ← AsyncEngine + get_db()
│       │   └── models/
│       │       ├── user.py     ← ORM Staff (doctor/secretary/admin)
│       │       └── patient.py  ← ORM Patient pseudonymisé
│       └── schemas/auth.py     ← Pydantic request/response schemas
└── alembic/versions/           ← Baseline migration s1_baseline_0001
```

### KPIs atteints

| Métrique | Cible | Résultat |
|----------|-------|----------|
| `/health` latence | < 2s | ~45ms |
| Login (bcrypt rounds=12) | < 1s | ~310ms |
| `/me` avec token valide | < 200ms | ~35ms |
| TLS version | TLS 1.3 | ✅ TLS 1.3 |
| Couverture tests | ≥ 80% | À compléter Sprint 2 |

---

## 2. US-01 — Infrastructure Docker (6 services)

### Ce qui a été fait

```yaml
# docker-compose.yml — structure simplifiée
services:
  postgres:   # PostgreSQL 16 + pgcrypto + uuid-ossp
  redis:      # Redis 7 avec AOF persistence + mot de passe
  fastapi:    # Application Python (bind-mount ./backend:/app pour hot-reload)
  qdrant:     # Base vectorielle (utilisée Sprint 3)
  ollama:     # Mistral 7B (utilisé Sprint 3)
  nginx:      # Reverse proxy TLS 1.3
```

### Décisions clés et pourquoi

**1. Healthchecks avec `condition: service_healthy`**
```yaml
fastapi:
  depends_on:
    postgres:
      condition: service_healthy   # attend que PostgreSQL accepte les connexions
    redis:
      condition: service_healthy
```
Sans ça, FastAPI démarre avant que PostgreSQL soit prêt → erreur de connexion au démarrage. C'est un bug classique des débutants Docker.

**2. Volumes nommés vs bind-mounts**
```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data  # nommé = données persistent
  - ./backend:/app                          # bind-mount = hot-reload dev
```
Le bind-mount `./backend:/app` est **uniquement pour le développement** — chaque modification de code Python est détectée par Uvicorn (`--reload`) sans rebuild de l'image.

**3. Réseau bridge isolé**
```yaml
networks:
  medisense_network:
    driver: bridge
```
Tous les services communiquent par nom (`fastapi` parle à `postgres`, pas à `localhost:5432`). Isolation réseau — les services ne sont pas exposés inutilement.

**4. Qdrant et Ollama provisionnés dès Sprint 1**
Même s'ils ne sont pas utilisés avant Sprint 3, les démarrer maintenant permet de :
- Valider que la machine a assez de RAM (Mistral 7B = 4.1 GB)
- Avoir l'infrastructure prête sans reconstruire la stack plus tard

---

## 3. US-02 — Sécurité HTTPS & Headers OWASP

### Ce qui a été fait

**Nginx — 3 rôles simultanés :**
1. **Terminaison TLS** — déchiffre HTTPS, communique en HTTP interne avec FastAPI
2. **Reverse proxy** — redirige `/api/*` et `/static/*` vers FastAPI port 8000
3. **Rate limiting** — protège contre brute-force et DDoS

```nginx
# nginx.conf — points clés
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;   # /auth/login
limit_req_zone $binary_remote_addr zone=api:10m  rate=60r/m;  # /api/

ssl_protocols TLSv1.3;   # TLS 1.3 uniquement — TLS 1.2 refusé
# Pas de ssl_ciphers → TLS 1.3 gère ses propres ciphers (AES-GCM-256, ChaCha20)
```

**FastAPI — Security Headers sur chaque réponse :**
```python
# main.py — middleware HTTP
response.headers["X-Frame-Options"] = "DENY"                    # anti-clickjacking
response.headers["X-Content-Type-Options"] = "nosniff"          # anti MIME-sniffing
response.headers["Strict-Transport-Security"] = "max-age=31536000"  # force HTTPS 1 an
# CSP strict pour les endpoints API, relaxé uniquement pour /docs
```

### Pourquoi TLS 1.3 et pas TLS 1.2 ?
- TLS 1.3 supprime les algorithmes faibles (RSA key exchange, CBC mode)
- Handshake en **1 aller-retour** au lieu de 2 → 30% plus rapide
- **Obligatoire pour données médicales** (RGPD + directive NIS2)

### Certificat auto-signé (dev uniquement)
```bash
bash scripts/generate_certs.sh   # génère medisense.crt + medisense.key
```
En production : Let's Encrypt via Certbot (automatique, gratuit, renouvelé toutes les 90 jours).

---

## 4. US-03 — Authentification JWT + Redis

### Architecture complète du flux

```
Client → POST /auth/login {email, password}
         │
         ├─ DB: SELECT user WHERE email = ?
         ├─ bcrypt.verify(password, hash) ← ~310ms intentionnellement lent
         │
         ├─ create_access_token()  → JWT signé HS256, exp=15min, contient {sub, role, jti}
         ├─ create_refresh_token() → JWT signé HS256, exp=7j,   contient {sub, role, jti}
         │
         └─ Response: {access_token, token_type:"bearer", expires_in:900}
```

### Anatomie d'un JWT access token (décodé)

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  ← UUID de l'utilisateur
  "role": "doctor",                                ← rôle RBAC
  "jti": "f47ac10b-58cc-4372-a567-0e02b2c3d479",  ← ID unique (pour révocation)
  "exp": 1743699600,                               ← expiration Unix timestamp
  "iat": 1743698700,                               ← émission Unix timestamp
  "type": "access"                                 ← distingue des refresh tokens
}
```

### Pourquoi le champ `jti` (JWT ID) ?

Les JWT sont **stateless par conception** — une fois émis, le serveur ne peut pas les "annuler". Le `jti` permet de contourner ça :

```python
# logout → ajoute le jti à Redis avec TTL = durée restante du token
async def blacklist_token(jti: str, expires_in_seconds: int):
    redis = await get_redis()
    await redis.setex(f"blacklist:{jti}", expires_in_seconds, "revoked")

# chaque requête vérifie si le jti est révoqué
async def is_token_blacklisted(jti: str) -> bool:
    redis = await get_redis()
    result = await redis.get(f"blacklist:{jti}")
    return result is not None
```

**Avantage Redis :** le TTL auto-expire → pas d'accumulation infinie de tokens révoqués.

### Pourquoi bcrypt rounds=12 ?

```python
pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)
# rounds=10 → ~100ms  (trop rapide → brute-force possible)
# rounds=12 → ~310ms  (acceptable pour login, prohibitif pour brute-force)
# rounds=14 → ~1200ms (trop lent → mauvaise UX)
```

**Calcul attaque brute-force :** avec rounds=12, tester 1 million de mots de passe = 310 000 secondes ≈ 3.5 jours sur 1 GPU. C'est le compromis performance/sécurité recommandé pour 2025-2026.

### Pourquoi `python-jose` et pas `PyJWT` ?

`python-jose` supporte nativement les algorithmes `RS256` (clé asymétrique) qu'on utilisera si on passe en production multi-service. `PyJWT` supporte aussi RS256 mais `python-jose` a une API plus simple pour les claims.

---

## 5. US-04 — RBAC : Contrôle d'Accès par Rôle

### Pattern FastAPI — Dependency Injection

Le RBAC est implémenté via le **système de dépendances de FastAPI** — le pattern le plus propre pour éviter de répéter du code d'auth dans chaque endpoint :

```python
# dependencies.py — le cœur du système

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> TokenPayload:
    # 1. Extrait le token du header "Authorization: Bearer eyJ..."
    # 2. Vérifie la signature JWT
    # 3. Vérifie l'expiration
    # 4. Vérifie que le type est "access" (pas refresh)
    # 5. Vérifie le blacklist Redis
    # → retourne TokenPayload{sub, role, jti}

def require_role(*allowed_roles: str):
    async def role_checker(
        current_user: TokenPayload = Depends(get_current_user)
    ) -> TokenPayload:
        if current_user.role not in allowed_roles:
            raise HTTPException(403, "Access denied")
        return current_user
    return role_checker

# Usage dans un endpoint :
@router.get("/patients")
async def get_patients(
    current_user = Depends(require_role("doctor", "admin"))
):
    # Si role != doctor ou admin → 403 automatiquement
    # Si token invalide → 401 automatiquement
    ...
```

### Tableau des permissions

```python
# security.py
ROLE_PERMISSIONS = {
    "admin":     {"/api/v1/admin", "/api/v1/patients", "/api/v1/appointments", "/api/v1/users"},
    "doctor":    {"/api/v1/patients", "/api/v1/appointments", "/api/v1/dpa", "/api/v1/alerts"},
    "secretary": {"/api/v1/appointments", "/api/v1/agenda"},
    "patient":   {"/api/v1/patient", "/api/v1/chat"},
}
```

### Pourquoi les patients ne sont pas dans `public.users` ?

Séparation conceptuelle importante :
- `public.users` = **staff de la clinique** (employés, compte email pro, mdp)
- Patients → **authentification différente** (ex: OTP SMS, pas de mot de passe en dur)
- Données patients = **sensibilité RGPD maximale** → schéma séparé

---

## 6. US-05 — Schéma RGPD + AES-256

### Architecture Privacy by Design

```sql
-- Schéma public : données pseudonymisées (UUID uniquement)
public.patients (
    patient_uuid UUID PRIMARY KEY,  ← seul identifiant dans ce schéma
    consent_iot  BOOLEAN,           ← consentement granulaire par catégorie
    consent_nlp  BOOLEAN,
    birth_year   SMALLINT,          ← année seulement (pas date complète)
    city_code    VARCHAR(10)        ← zone postale, pas adresse complète
    -- AUCUN nom, prénom, téléphone, email ici
)

-- Schéma secure : identité chiffrée AES-256
secure.patients_identity (
    patient_uuid UUID PRIMARY KEY REFERENCES public.patients,
    full_name_enc BYTEA,  ← pgp_sym_encrypt(full_name, $key)
    phone_enc     BYTEA,
    email_enc     BYTEA
)
```

### Pourquoi 2 schémas PostgreSQL séparés ?

**Principe du moindre privilège :**
- Le code qui lit `public.patients` (pour le ML, les RDV) n'a **jamais accès** à `secure.*`
- Seul le endpoint DPO (Sprint 2) peut déchiffrer l'identité civile
- Si une faille SQL injection touche l'API principale → l'identité civile reste chiffrée

### Comment fonctionne pgcrypto AES-256 ?

```sql
-- Chiffrement (à l'écriture)
INSERT INTO secure.patients_identity (patient_uuid, full_name_enc)
VALUES (
    '550e8400-...',
    pgp_sym_encrypt('Ahmed Benali', current_setting('app.pgcrypto_key'))
);

-- Déchiffrement (lecture — uniquement par le DPO endpoint)
SELECT pgp_sym_decrypt(full_name_enc, current_setting('app.pgcrypto_key'))
FROM secure.patients_identity
WHERE patient_uuid = '550e8400-...';
```

La clé `pgcrypto_key` vient de la **variable d'environnement** `.env` — jamais stockée dans la DB.

### Tables immuables — Règles PostgreSQL

```sql
-- audit_logs et consent_logs : APPEND-ONLY
-- aucun UPDATE ni DELETE possible, même pour l'admin
CREATE RULE audit_no_update AS ON UPDATE TO public.audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO public.audit_logs DO INSTEAD NOTHING;
```

**Pourquoi ?** RGPD Art. 30 exige un registre des traitements **non falsifiable**. Si un admin peut supprimer un log d'accès, le registre perd sa valeur légale.

---

## 7. US-45 — Swagger UI (assets locaux)

### Problème résolu

FastAPI charge par défaut ses assets Swagger depuis `cdn.jsdelivr.net`. Derrière un certificat auto-signé + CSP strict → le navigateur bloque les requêtes externes → page blanche.

### Solution en 3 parties

**1. Téléchargement des assets à la construction Docker**
```dockerfile
ARG SWAGGER_UI_VERSION=5.11.0
RUN curl -fsSL "https://cdn.jsdelivr.net/npm/swagger-ui-dist@${SWAGGER_UI_VERSION}/swagger-ui.css" \
         -o /app/static/swagger-ui.css && \
    curl -fsSL "https://cdn.jsdelivr.net/npm/swagger-ui-dist@${SWAGGER_UI_VERSION}/swagger-ui-bundle.js" \
         -o /app/static/swagger-ui-bundle.js
# -fsSL : fail loudly si le CDN est down (évite fichiers vides silencieux)
```

**2. Route `/docs` personnalisée** (FastAPI 0.115+ ne supporte plus `swagger_js_url` dans `__init__`)
```python
app = FastAPI(docs_url=None)  # désactive la route par défaut

@app.get("/api/v1/docs", include_in_schema=False)
async def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        swagger_js_url="/static/swagger-ui-bundle.js",   # assets locaux
        swagger_css_url="/static/swagger-ui.css",
    )

@app.get("/api/v1/docs/oauth2-redirect", include_in_schema=False)
async def oauth2_redirect():
    return get_swagger_ui_oauth2_redirect_html()   # nécessaire pour le flow OAuth2
```

**3. Nginx — bloc `/static/`**
```nginx
location /static/ {
    proxy_pass http://fastapi_backend;  # sans ça : 404 sur les assets
    expires 1d;
    add_header Cache-Control "public, immutable";
}
```

---

## 8. Bugs résolus & Leçons Apprises

| # | Bug | Cause | Fix | Leçon |
|---|-----|-------|-----|-------|
| 1 | `ModuleNotFoundError: email_validator` | `pip install --no-deps` ne résout pas les dépendances transitives | Ajouter `email-validator==2.2.0` explicitement dans `requirements.txt` | Avec `--no-deps` dans Dockerfile, **tout** doit être listé explicitement |
| 2 | `nginx: [emerg] limit_req_zone not allowed here` | `limit_req_zone` placé dans `server{}` | Déplacer dans `http{}` | Directives nginx = scope strict : `http > server > location` |
| 3 | `SSL_CTX_set_cipher_list: no cipher can be selected` | `ssl_ciphers` ne comprend pas les ciphers TLS 1.3 | Supprimer `ssl_ciphers` — TLS 1.3 les gère seul | TLS 1.3 et TLS 1.2 ont des mécanismes de configuration différents |
| 4 | `LookupError: 'admin' is not among defined enum values` | SQLAlchemy stocke le nom de l'enum (`ADMIN`) pas la valeur (`admin`) | `values_callable=lambda x: [e.value for e in x]` | SQLAlchemy Enum : toujours spécifier `native_enum=False` + `values_callable` |
| 5 | `401 Incorrect email or password` sur admin existant | Hash bcrypt dans `init_db.sql` ne correspondait pas à `Admin1234!` | Régénérer le hash dans le container et UPDATE SQL | Ne jamais copier-coller un hash bcrypt — le générer depuis le code |
| 6 | `ValidationError: user_uuid: str type expected` | `UserResponse.user_uuid: str` rejetait l'objet UUID de SQLAlchemy | Changer en `user_uuid: UUID` (depuis `uuid`) | Pydantic v2 sait convertir `UUID → str` en JSON, mais le type interne doit être `UUID` |
| 7 | Swagger UI page blanche | Assets CDN bloqués par certificat auto-signé + CSP | Assets locaux + route custom + bloc nginx `/static/` | Toujours tester Swagger derrière HTTPS dès le début |

---

## 9. Ce sur quoi tu dois te concentrer — Profil DS/IA

> En tant que profil **Data Science & IA** (RAG, LSTM, XGBoost, Kafka), certaines parties de Sprint 1 sont des fondations que tu vas **utiliser chaque jour** dans les sprints suivants. D'autres sont du "plomberie" que tu n'as pas besoin de maîtriser parfaitement maintenant.

### 🔴 CRITIQUE — Comprendre absolument

#### 1. Le pattern `Depends()` de FastAPI
C'est le mécanisme que tu vas utiliser **dans chaque endpoint IA** pour protéger l'accès :

```python
# Sprint 3 — endpoint chat RAG
@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: TokenPayload = Depends(require_role("patient")),  # ← Sprint 1
    db: AsyncSession = Depends(get_db),                              # ← Sprint 1
):
    # Vérifier le consentement NLP avant d'appeler Mistral
    if not patient.consent_nlp:     # ← Sprint 2 (RGPD)
        raise HTTPException(403, "Consentement NLP requis")
    # Appel RAG...
```

Retiens : **`Depends()` = injection de dépendance**. C'est comme un `@login_required` de Django mais composable et testable.

#### 2. Le consentement RGPD gate l'IA

```python
# Logique que tu vas écrire dans CHAQUE pipeline IA
if not patient.consent_iot:
    # Ne pas envoyer les données biométriques au LSTM
    raise HTTPException(403, "Consentement IoT requis")

if not patient.consent_nlp:
    # Ne pas appeler Qdrant ni Mistral
    raise HTTPException(403, "Consentement NLP requis")
```

Les champs `consent_iot`, `consent_nlp`, `consent_sharing` dans `public.patients` sont les **interrupteurs qui activent ou bloquent tes pipelines IA**. C'est du Sprint 1 qui impacte directement Sprint 3, 4, 7.

#### 3. L'`AsyncSession` SQLAlchemy

```python
# Pattern de base que tu vas répéter partout
async def get_patients_for_ml(db: AsyncSession):
    result = await db.execute(
        select(Patient)
        .where(Patient.consent_iot == True)
        .where(Patient.is_active == True)
    )
    return result.scalars().all()
```

Comprends que `await` est **obligatoire** avec `asyncpg`. Si tu oublies un `await` → l'appel retourne une coroutine non exécutée (bug silencieux difficile à détecter).

#### 4. La structure des schémas Pydantic

```python
# Sprint 3 — tu vas créer des schémas similaires
class ChatRequest(BaseModel):
    message: str
    language: Literal["fr", "ar", "darija"] = "fr"

class ChatResponse(BaseModel):
    response: str
    sources: list[str]
    latency_ms: float
    confidence: float
```

Pydantic v2 valide **automatiquement** les types, génère le schéma OpenAPI pour Swagger, et protège contre les injections de données malformées.

---

### 🟠 IMPORTANT — Comprendre le principe, pas les détails

#### 5. JWT — tu l'utilises sans le recoder
Le token est généré dans `core/security.py`. Dans tes endpoints IA, tu reçois directement le `TokenPayload` via `Depends(get_current_user)` qui contient déjà `sub` (UUID user) et `role`. Tu n'interagis jamais avec le JWT brut.

#### 6. Le schéma RGPD — tu ne lis jamais `secure.*`
Tes modèles ML (XGBoost, LSTM) travaillent sur `public.patients` (pseudonymisé). Tu utilises `patient_uuid`, `birth_year`, `chronic_conditions` — jamais le nom ni le téléphone. C'est **voulu** par design.

#### 7. Redis — tu vas l'utiliser pour autre chose
Sprint 1 utilise Redis pour le blacklist JWT. Sprint 3 l'utilisera pour la **mémoire de conversation** (historique du chatbot). C'est le même Redis, namespace différent :
```
blacklist:{jti}         ← Sprint 1 (auth)
conv:{patient_uuid}     ← Sprint 3 (RAG memory)
cache:rag:{query_hash}  ← Sprint 3 (cache réponses fréquentes)
```

---

### 🟢 PEUT ATTENDRE — Infrastructure, reviens si problème

- Détails de la config Nginx (tu n'y touches plus jusqu'à Sprint 6)
- Détails du Dockerfile multi-stage (stable pour toute la durée du PFE)
- Configuration Alembic (tu vas ajouter des migrations à chaque sprint mais le setup est fait)
- Détails de la config PostgreSQL (gérée par Docker)

---

### Plan de révision avant Sprint 2

**Exercice pratique recommandé (30 min) :**

```bash
# 1. Lance la stack
docker compose up -d

# 2. Teste le login
curl -k -X POST https://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medisense.ai","password":"Admin1234!"}'
# → Copie l'access_token

# 3. Appelle /me
curl -k https://localhost/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
# → Tu vois le profil admin

# 4. Décode ton JWT sur https://jwt.io
# → Lis les claims : sub, role, jti, exp, type
# → Comprends pourquoi le token expire dans 15 min

# 5. Fais un logout
curl -k -X POST https://localhost/api/v1/auth/logout \
  -H "Authorization: Bearer <access_token>"
# → Essaie de réutiliser le même token → 401 "Token has been revoked"
```

**Questions à être capable de répondre :**
1. Pourquoi le login retourne 401 si l'email n'existe pas **ET** si le mot de passe est faux (même message) ?
2. Que se passe-t-il si tu envoies un refresh_token dans le header `Authorization: Bearer` à la place d'un access_token ?
3. Pourquoi `consent_iot` est dans `public.patients` et pas dans `secure.patients_identity` ?
4. Comment ajouter un nouvel endpoint `/api/v1/patients` accessible uniquement aux `doctor` et `admin` ?

---

### Ce que Sprint 1 débloque pour ton profil DS/IA

```
Sprint 1 (fait) → Sprint 2 (RGPD) → Sprint 3 (RAG)
     ↓                  ↓                ↓
  AsyncSession       consent_nlp      Qdrant + Mistral
  require_role()     audit_log        Redis conv memory
  TokenPayload       /export data     Streaming response
     ↓
Sprint 5 (ML)       Sprint 7 (IoT)
     ↓                  ↓
  predict endpoint    LSTM inference
  XGBoost model       TimescaleDB
  SHAP values         Kafka consumer
```

**Tout ce que tu construis en IA passera par le même `Depends(require_role(...))` et le même `AsyncSession` que tu as appris en Sprint 1.** C'est le socle.
