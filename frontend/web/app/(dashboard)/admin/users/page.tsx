'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashButton } from '@/components/dash-button';
import { StatusBadge } from '@/components/status-badge';
import { DashPage } from '@/components/dashboard-shell';
import { IconMore, IconClose } from '@/components/icons';

type UserRole = 'doctor' | 'secretary' | 'admin' | 'patient';

interface ApiUser {
  user_uuid: string;
  email: string;
  role: UserRole;
  first_name: string | null;
  last_name: string | null;
  is_active: boolean;
  created_at: string;
  mfa_enabled?: boolean;
  last_login?: string | null;
}

const ROLE_STYLES: Record<UserRole, { color: string; bg: string; bd: string; ring: string }> = {
  admin: {
    color: '#fff',
    bg: 'rgba(139,92,246,0.20)', bd: 'rgba(139,92,246,0.40)',
    ring: 'var(--ai-grad)',
  },
  doctor: {
    color: '#38BDF8',
    bg: 'rgba(56,189,248,0.10)', bd: 'rgba(56,189,248,0.40)',
    ring: 'rgba(56,189,248,0.20)',
  },
  secretary: {
    color: '#A78BFA',
    bg: 'rgba(167,139,250,0.10)', bd: 'rgba(167,139,250,0.40)',
    ring: 'rgba(167,139,250,0.20)',
  },
  patient: {
    color: '#22C55E',
    bg: 'rgba(34,197,94,0.10)', bd: 'rgba(34,197,94,0.40)',
    ring: 'rgba(34,197,94,0.20)',
  },
};

function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const today = new Date();
  const same = d.toDateString() === today.toDateString();
  const yest = new Date(today); yest.setDate(today.getDate() - 1);
  const isYest = d.toDateString() === yest.toDateString();
  const hh = d.getHours().toString().padStart(2, '0');
  const mm = d.getMinutes().toString().padStart(2, '0');
  if (same) return `${hh}:${mm} aujourd'hui`;
  if (isYest) return `hier · ${hh}:${mm}`;
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) + ` · ${hh}:${mm}`;
}

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '', password: '',
    role: 'doctor' as UserRole, forceMfa: true,
  });
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const { data, isLoading, isError } = useQuery<{ total: number; items: ApiUser[] }>({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const { data } = await api.get('/admin/users?limit=100');
      return data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post('/admin/users', {
        email: form.email,
        password: form.password,
        role: form.role,
        first_name: form.firstName || null,
        last_name: form.lastName || null,
      });
      return data as ApiUser;
    },
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      setShowModal(false);
      setForm({ firstName: '', lastName: '', email: '', password: '', role: 'doctor', forceMfa: true });
      showToast(`Compte créé : ${user.email}`);
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(detail || 'Erreur lors de la création.', false);
    },
  });

  const users = data?.items ?? [];
  const total = data?.total ?? 0;

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: 10,
    background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
    color: 'var(--t0)', fontFamily: 'var(--f-body)', fontSize: 13, outline: 'none',
    boxSizing: 'border-box',
  };

  const canSubmit = form.email && form.password.length >= 8 && !createMutation.isPending;

  return (
    <>
      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 9999,
          background: toast.ok ? '#22C55E20' : '#EF444420',
          border: `1px solid ${toast.ok ? '#22C55E40' : '#EF444440'}`,
          color: toast.ok ? '#22C55E' : '#EF4444',
          padding: '10px 18px', borderRadius: 10, fontSize: 13, fontWeight: 500,
          animation: 'slide-down 0.2s ease',
        }}>
          {toast.msg}
        </div>
      )}

      {/* Create modal */}
      {showModal && (
        <div
          style={{
            position: 'fixed', inset: 0, zIndex: 9000,
            background: 'rgba(0,0,0,0.60)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={() => setShowModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 420, background: 'var(--s1)', border: '1px solid var(--line-strong)',
              borderRadius: 16, padding: 24, boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
              animation: 'spring-in 0.35s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
              <h3 style={{ fontFamily: 'var(--f-display)', fontSize: 18, fontWeight: 600, color: 'var(--t0)', margin: 0 }}>
                Créer un compte
              </h3>
              <button onClick={() => setShowModal(false)} style={{
                background: 'none', border: 'none', color: 'var(--t3)', cursor: 'pointer', padding: 0,
              }}>
                <IconClose size={16} />
              </button>
            </div>

            <div style={{ display: 'grid', gap: 12 }}>
              <div style={{ display: 'flex', gap: 10 }}>
                <input
                  placeholder="Prénom"
                  value={form.firstName}
                  onChange={(e) => setForm((f) => ({ ...f, firstName: e.target.value }))}
                  style={inputStyle}
                />
                <input
                  placeholder="Nom"
                  value={form.lastName}
                  onChange={(e) => setForm((f) => ({ ...f, lastName: e.target.value }))}
                  style={inputStyle}
                />
              </div>
              <input
                type="email"
                placeholder="email@medisense.ma"
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                style={inputStyle}
              />
              <input
                type="password"
                placeholder="Mot de passe temporaire (≥ 8 car.)"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                style={inputStyle}
              />
              <select
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as UserRole }))}
                style={{ ...inputStyle, cursor: 'pointer' }}
              >
                <option value="doctor">doctor</option>
                <option value="secretary">secretary</option>
                <option value="admin">admin</option>
                <option value="patient">patient</option>
              </select>
              <label style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--t1)', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={form.forceMfa}
                  onChange={(e) => setForm((f) => ({ ...f, forceMfa: e.target.checked }))}
                />
                Forcer l&apos;activation MFA
              </label>
              <label style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--t1)', alignItems: 'center' }}>
                <input type="checkbox" defaultChecked /> Envoyer email d&apos;invitation
              </label>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 18, justifyContent: 'flex-end' }}>
              <DashButton kind="ghost" onClick={() => setShowModal(false)}>Annuler</DashButton>
              <DashButton kind="gradient" disabled={!canSubmit} onClick={() => createMutation.mutate()}>
                {createMutation.isPending ? 'Création…' : 'Créer le compte'}
              </DashButton>
            </div>
          </div>
        </div>
      )}

      <DashPage
        breadcrumb="comptes · gestion"
        title="Gestion des utilisateurs"
        subtitle={`Création, désactivation, MFA · ${total} compte${total !== 1 ? 's' : ''} au total`}
        actions={
          <>
            <DashButton kind="solid" small>Inviter par email</DashButton>
            <DashButton
              kind="gradient"
              small
              onClick={() => setShowModal(true)}
              icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14"/></svg>}
            >
              Créer un compte
            </DashButton>
          </>
        }
      >
        {/* Table */}
        <div style={{
          background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
        }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '40px 1.5fr 110px 90px 80px 1fr 60px',
            padding: '11px 18px', background: 'var(--s2)',
            fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
            letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 500,
            borderBottom: '1px solid var(--line)',
          }}>
            <div></div>
            <div>Email</div>
            <div>Rôle</div>
            <div>Statut</div>
            <div>MFA</div>
            <div>Dernière connexion</div>
            <div></div>
          </div>

          {isLoading && (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>Chargement…</div>
          )}
          {isError && (
            <div style={{ padding: 40, textAlign: 'center', color: '#EF4444', fontSize: 13 }}>
              Erreur de chargement des utilisateurs.
            </div>
          )}

          {!isLoading && !isError && users.length === 0 && (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
              Aucun utilisateur trouvé.
            </div>
          )}

          {!isLoading && !isError && users.map((u, i) => {
            const styles = ROLE_STYLES[u.role] ?? ROLE_STYLES.patient;
            const mfa = u.mfa_enabled ?? false;
            return (
              <div
                key={u.user_uuid}
                style={{
                  display: 'grid', gridTemplateColumns: '40px 1.5fr 110px 90px 80px 1fr 60px',
                  padding: '13px 18px', alignItems: 'center',
                  borderBottom: i < users.length - 1 ? '1px solid var(--line)' : 'none',
                  opacity: u.is_active ? 1 : 0.55,
                  transition: 'background 0.14s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(99,102,241,0.04)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <div style={{
                  width: 28, height: 28, borderRadius: 99,
                  background: styles.ring,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'var(--f-display)', fontSize: 12, fontWeight: 600,
                  color: styles.color,
                }}>
                  {u.email[0].toUpperCase()}
                </div>
                <div style={{ fontSize: 13, color: 'var(--t0)', fontFamily: 'var(--f-mono)' }}>{u.email}</div>
                <div>
                  <span style={{
                    fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                    letterSpacing: '0.10em', textTransform: 'uppercase',
                    padding: '3px 9px', borderRadius: 99,
                    color: styles.color, background: styles.bg, border: `1px solid ${styles.bd}`,
                  }}>
                    {u.role}
                  </span>
                </div>
                <div>
                  <StatusBadge
                    tone={u.is_active ? 'sent' : 'skipped'}
                    label={u.is_active ? 'Actif' : 'Désactivé'}
                  />
                </div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 11,
                  color: mfa ? '#22C55E' : 'var(--t4)',
                }}>
                  {mfa ? '✓ activé' : '— off'}
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>
                  {formatRelative(u.last_login ?? u.created_at)}
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', position: 'relative' }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenMenu(openMenu === u.user_uuid ? null : u.user_uuid);
                    }}
                    style={{
                      width: 28, height: 28, borderRadius: 6, cursor: 'pointer',
                      background: 'transparent', border: '1px solid var(--line)',
                      color: 'var(--t3)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    <IconMore size={14} />
                  </button>
                  {openMenu === u.user_uuid && (
                    <div
                      style={{
                        position: 'absolute', right: 0, top: '100%', zIndex: 100,
                        background: 'var(--s2)', border: '1px solid var(--line-strong)',
                        borderRadius: 8, padding: 4, minWidth: 160, marginTop: 4,
                        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {['Réinitialiser MDP', u.is_active ? 'Suspendre' : 'Activer', 'Voir les audits'].map((label) => (
                        <button
                          key={label}
                          onClick={() => setOpenMenu(null)}
                          style={{
                            display: 'block', width: '100%', padding: '7px 12px',
                            background: 'transparent', border: 'none', color: 'var(--t1)',
                            fontSize: 12.5, textAlign: 'left', cursor: 'pointer', borderRadius: 5,
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--s3)')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </DashPage>
    </>
  );
}
