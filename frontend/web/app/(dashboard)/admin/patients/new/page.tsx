'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashPage } from '@/components/dashboard-shell';
import { DashButton } from '@/components/dash-button';
import { IconClose } from '@/components/icons';

interface PatientOut {
  patient_uuid: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  birth_year: number | null;
  sex: string | null;
  city_code: string | null;
  chronic_conditions: string[];
  is_active: boolean;
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px',
  background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
  color: 'var(--t0)', fontFamily: 'var(--f-body)', fontSize: 13, outline: 'none',
  boxSizing: 'border-box',
};

const labelStyle: React.CSSProperties = {
  fontSize: 11, fontFamily: 'var(--f-mono)', letterSpacing: '0.08em',
  textTransform: 'uppercase', color: 'var(--t3)', fontWeight: 600,
  display: 'block', marginBottom: 5,
};

export default function NewPatientPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    email: '',
    password: '',
    firstName: '',
    lastName: '',
    birthYear: '',
    sex: '' as '' | 'M' | 'F',
    cityCode: '',
  });
  const [conditions, setConditions] = useState<string[]>([]);
  const [conditionInput, setConditionInput] = useState('');
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const addCondition = () => {
    const val = conditionInput.trim();
    if (val && !conditions.includes(val)) {
      setConditions((prev) => [...prev, val]);
    }
    setConditionInput('');
  };

  const removeCondition = (c: string) =>
    setConditions((prev) => prev.filter((x) => x !== c));

  const mutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<PatientOut>('/admin/patients', {
        email: form.email,
        password: form.password,
        first_name: form.firstName || null,
        last_name: form.lastName || null,
        birth_year: form.birthYear ? parseInt(form.birthYear, 10) : null,
        sex: form.sex || null,
        city_code: form.cityCode || null,
        chronic_conditions: conditions,
      });
      return data;
    },
    onSuccess: (patient) => {
      showToast(`Patient créé : ${patient.email}`);
      setTimeout(() => router.push('/patients'), 1200);
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(detail || 'Erreur lors de la création.', false);
    },
  });

  const canSubmit = form.email && form.password.length >= 8 && !mutation.isPending;

  return (
    <>
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 9999,
          background: toast.ok ? '#22C55E20' : '#EF444420',
          border: `1px solid ${toast.ok ? '#22C55E40' : '#EF444440'}`,
          color: toast.ok ? '#22C55E' : '#EF4444',
          padding: '10px 18px', borderRadius: 10, fontSize: 13, fontWeight: 500,
        }}>
          {toast.msg}
        </div>
      )}

      <DashPage
        breadcrumb="patients · nouveau"
        title="Nouveau patient"
        subtitle="Crée un compte patient avec User + Patient atomiquement (même UUID)"
        actions={
          <DashButton kind="ghost" small onClick={() => router.push('/patients')}>
            Annuler
          </DashButton>
        }
      >
        <div style={{ maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Identity */}
          <Section title="Identité">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Field label="Prénom">
                <input
                  style={inputStyle}
                  placeholder="Fatima"
                  value={form.firstName}
                  onChange={(e) => setForm((f) => ({ ...f, firstName: e.target.value }))}
                />
              </Field>
              <Field label="Nom">
                <input
                  style={inputStyle}
                  placeholder="Alaoui"
                  value={form.lastName}
                  onChange={(e) => setForm((f) => ({ ...f, lastName: e.target.value }))}
                />
              </Field>
            </div>
            <Field label="Email *">
              <input
                type="email"
                style={inputStyle}
                placeholder="patient@clinique.ma"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </Field>
            <Field label="Mot de passe temporaire * (≥ 8 car.)">
              <input
                type="password"
                style={inputStyle}
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </Field>
          </Section>

          {/* ML Demographics */}
          <Section title="Démographie (modèle ML)">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
              <Field label="Année de naissance">
                <input
                  type="number"
                  style={inputStyle}
                  placeholder="1985"
                  min={1900}
                  max={2025}
                  value={form.birthYear}
                  onChange={(e) => setForm((f) => ({ ...f, birthYear: e.target.value }))}
                />
              </Field>
              <Field label="Sexe">
                <select
                  style={{ ...inputStyle, cursor: 'pointer' }}
                  value={form.sex}
                  onChange={(e) => setForm((f) => ({ ...f, sex: e.target.value as '' | 'M' | 'F' }))}
                >
                  <option value="">—</option>
                  <option value="M">M</option>
                  <option value="F">F</option>
                </select>
              </Field>
              <Field label="Code ville">
                <input
                  style={inputStyle}
                  placeholder="40000"
                  value={form.cityCode}
                  onChange={(e) => setForm((f) => ({ ...f, cityCode: e.target.value }))}
                />
              </Field>
            </div>

            <Field label="Maladies chroniques (Entrée pour ajouter)">
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  style={{ ...inputStyle, flex: 1 }}
                  placeholder="ex: hypertension"
                  value={conditionInput}
                  onChange={(e) => setConditionInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); addCondition(); }
                  }}
                />
                <button
                  onClick={addCondition}
                  style={{
                    padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
                    background: 'var(--s2)', border: '1px solid var(--line)',
                    color: 'var(--t1)', fontSize: 12, whiteSpace: 'nowrap',
                  }}
                >
                  Ajouter
                </button>
              </div>
              {conditions.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                  {conditions.map((c) => (
                    <span key={c} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      padding: '4px 10px', borderRadius: 99,
                      background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.30)',
                      color: '#A78BFA', fontSize: 11.5, fontFamily: 'var(--f-mono)',
                    }}>
                      {c}
                      <button
                        onClick={() => removeCondition(c)}
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer',
                          color: '#A78BFA', padding: 0, lineHeight: 1,
                        }}
                      >
                        <IconClose size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </Field>
          </Section>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <DashButton kind="ghost" onClick={() => router.push('/patients')}>
              Annuler
            </DashButton>
            <DashButton
              kind="gradient"
              disabled={!canSubmit}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? 'Création…' : 'Créer le patient'}
            </DashButton>
          </div>
        </div>
      </DashPage>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--line)',
      borderRadius: 14, padding: '18px 20px',
      display: 'flex', flexDirection: 'column', gap: 12,
    }}>
      <p style={{
        margin: 0, fontSize: 10, fontFamily: 'var(--f-mono)',
        letterSpacing: '0.10em', textTransform: 'uppercase',
        color: 'var(--t3)', fontWeight: 600,
      }}>
        {title}
      </p>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}
