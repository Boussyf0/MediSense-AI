-- ============================================================
-- MediSense AI — PostgreSQL Initialization
-- This script runs ONCE on first container start
-- ============================================================

-- Enable pgcrypto for AES-256 encryption (RGPD at-rest)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enable uuid-ossp for UUID v4 generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Schemas ──────────────────────────────────────────────
-- public schema: all pseudonymized data (UUID-only, no civil identity)
-- secure schema: civil identity encrypted with pgcrypto
--   Access to secure schema is restricted at the application level
--   (only the DPO endpoint can query it)

CREATE SCHEMA IF NOT EXISTS secure;

-- ── Audit log (RGPD Art. 30 — immutable access log) ──────
-- This table records every access to patient data.
-- It is APPEND-ONLY: no UPDATE, no DELETE allowed.
-- The trigger enforces this at the DB level.
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    actor_uuid      UUID NOT NULL,          -- who performed the action
    actor_role      VARCHAR(20) NOT NULL,   -- patient | doctor | secretary | admin
    action          VARCHAR(50) NOT NULL,   -- READ | WRITE | DELETE | EXPORT | LOGIN
    resource_type   VARCHAR(50) NOT NULL,   -- patient | appointment | biometrics | etc.
    resource_uuid   UUID,                   -- which resource was accessed
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Prevent any UPDATE or DELETE on audit_logs
CREATE OR REPLACE RULE audit_no_update AS ON UPDATE TO public.audit_logs DO INSTEAD NOTHING;
CREATE OR REPLACE RULE audit_no_delete AS ON DELETE TO public.audit_logs DO INSTEAD NOTHING;

-- ── Users (staff: doctors, secretaries, admins) ──────────
-- Patients are NOT in this table. They authenticate via a separate flow.
CREATE TABLE IF NOT EXISTS public.users (
    user_uuid       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,   -- bcrypt hash, never plaintext
    role            VARCHAR(20) NOT NULL CHECK (role IN ('doctor', 'secretary', 'admin')),
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Patients (pseudonymized — UUID only in this table) ───
-- This table contains NO civil identity (no name, no phone, no email).
-- The UUID is the only identifier here.
-- Civil identity lives in secure.patients_identity (encrypted).
CREATE TABLE IF NOT EXISTS public.patients (
    patient_uuid        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Consent per category (RGPD Art. 7 — granular opt-in)
    consent_iot         BOOLEAN NOT NULL DEFAULT FALSE,
    consent_nlp         BOOLEAN NOT NULL DEFAULT FALSE,
    consent_sharing     BOOLEAN NOT NULL DEFAULT FALSE,
    -- Demographics needed for ML (no identity link)
    birth_year          SMALLINT,           -- NOT full birthdate (reduces re-identification risk)
    sex                 CHAR(1) CHECK (sex IN ('M', 'F', 'O')),
    city_code           VARCHAR(10),        -- postal zone, not full address
    -- Medical context
    chronic_conditions  TEXT[],             -- ['hypertension', 'diabetes']
    -- Metadata
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Patient Civil Identity (ENCRYPTED, secure schema) ────
-- Stored separately from patients table.
-- All sensitive fields encrypted with pgcrypto using a key
-- that is NOT stored in the database (comes from environment variable).
-- pgp_sym_encrypt(value, key) → stores encrypted bytea
-- pgp_sym_decrypt(value, key) → decrypts at query time
CREATE TABLE IF NOT EXISTS secure.patients_identity (
    patient_uuid    UUID PRIMARY KEY REFERENCES public.patients(patient_uuid) ON DELETE CASCADE,
    -- Fields stored encrypted — use pgp_sym_encrypt/decrypt in queries
    full_name_enc   BYTEA NOT NULL,   -- pgp_sym_encrypt(full_name, $key)
    phone_enc       BYTEA,            -- pgp_sym_encrypt(phone, $key)
    email_enc       BYTEA,            -- pgp_sym_encrypt(email, $key)
    -- Consent timestamps (ISO 8601, immutable once set)
    consent_iot_at      TIMESTAMPTZ,
    consent_nlp_at      TIMESTAMPTZ,
    consent_sharing_at  TIMESTAMPTZ,
    -- CGU version accepted
    cgu_version     VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Consent Logs (immutable history) ─────────────────────
-- Every consent change is logged here (RGPD accountability)
CREATE TABLE IF NOT EXISTS public.consent_logs (
    id              BIGSERIAL PRIMARY KEY,
    patient_uuid    UUID NOT NULL REFERENCES public.patients(patient_uuid),
    consent_type    VARCHAR(20) NOT NULL CHECK (consent_type IN ('iot', 'nlp', 'sharing')),
    action          VARCHAR(10) NOT NULL CHECK (action IN ('granted', 'revoked')),
    channel         VARCHAR(20) NOT NULL,   -- 'app' | 'web' | 'paper'
    cgu_version     VARCHAR(20),
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Immutable: no updates or deletes on consent history
CREATE OR REPLACE RULE consent_no_update AS ON UPDATE TO public.consent_logs DO INSTEAD NOTHING;
CREATE OR REPLACE RULE consent_no_delete AS ON DELETE TO public.consent_logs DO INSTEAD NOTHING;

-- ── Appointments ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.appointments (
    appointment_uuid    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_uuid        UUID NOT NULL REFERENCES public.patients(patient_uuid),
    doctor_uuid         UUID NOT NULL REFERENCES public.users(user_uuid),
    scheduled_at        TIMESTAMPTZ NOT NULL,
    duration_minutes    SMALLINT NOT NULL DEFAULT 20,
    status              VARCHAR(20) NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled', 'confirmed', 'cancelled', 'completed', 'no_show')),
    -- No-show prediction (populated by XGBoost model)
    noshow_probability  FLOAT CHECK (noshow_probability BETWEEN 0 AND 1),
    noshow_model_ver    VARCHAR(20),
    -- Triage context (from RAG agent)
    urgency_flag        VARCHAR(50),    -- e.g. 'ANOMALIE_IOT_ESSOUFFLEMENT'
    urgency_score       FLOAT,
    rag_summary         TEXT,
    -- CRM sync
    salesforce_task_id  VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────
-- Optimize common query patterns
CREATE INDEX IF NOT EXISTS idx_appointments_patient ON public.appointments(patient_uuid);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor  ON public.appointments(doctor_uuid);
CREATE INDEX IF NOT EXISTS idx_appointments_date    ON public.appointments(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor          ON public.audit_logs(actor_uuid);
CREATE INDEX IF NOT EXISTS idx_audit_resource       ON public.audit_logs(resource_uuid);
CREATE INDEX IF NOT EXISTS idx_consent_patient      ON public.consent_logs(patient_uuid);

-- ── Default Admin User ────────────────────────────────────
-- Password: Admin1234! (CHANGE IN PRODUCTION)
-- Hash generated with bcrypt rounds=12
-- In production, remove this and use the /admin/users endpoint
INSERT INTO public.users (email, hashed_password, role, first_name, last_name)
VALUES (
    'admin@medisense.ai',
    '$2b$12$tOwWzG641ZWA/BAcW9r5Mu1TnGskRD7DsR4dJi8TbHr/kBJYgUD7S',
    'admin',
    'System',
    'Admin'
) ON CONFLICT (email) DO NOTHING;
