'use client';
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashPage } from '@/components/dashboard-shell';
import { DashButton } from '@/components/dash-button';
import { StatusBadge } from '@/components/status-badge';

interface PatientListItem {
  patient_uuid: string;
  birth_year: number | null;
  sex: string | null;
  city_code: string | null;
  chronic_conditions: string[] | null;
  is_active: boolean;
  last_appointment_at: string | null;
  next_appointment_at: string | null;
}

interface PatientListResponse {
  items: PatientListItem[];
  total: number;
  limit: number;
  offset: number;
}

const PAGE_SIZE = 50;

function ageFrom(birthYear: number | null): string {
  if (!birthYear) return '—';
  const age = new Date().getFullYear() - birthYear;
  return `${age} ans`;
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function shortUuid(uuid: string): string {
  return uuid.slice(0, 8);
}

export default function PatientsPage() {
  const [search, setSearch] = useState('');
  const [onlyActive, setOnlyActive] = useState(true);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<PatientListResponse>({
    queryKey: ['patients', { onlyActive }],
    queryFn: async () => {
      const { data } = await api.get('/patients', {
        params: { limit: PAGE_SIZE, offset: 0, only_active: onlyActive },
      });
      return data;
    },
  });

  const filtered = useMemo(() => {
    const rows = data?.items ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) =>
      r.patient_uuid.toLowerCase().includes(q) ||
      (r.city_code ?? '').toLowerCase().includes(q) ||
      (r.chronic_conditions ?? []).some((c) => c.toLowerCase().includes(q)),
    );
  }, [data, search]);

  return (
    <DashPage
      breadcrumb="patients"
      title="Patients"
      subtitle={
        data
          ? `${data.total} patient${data.total > 1 ? 's' : ''} ${onlyActive ? 'actifs' : 'au total'}`
          : 'Roster clinique — RGPD pseudonymisé'
      }
      actions={
        <Link href="/admin/patients/new" style={{ textDecoration: 'none' }}>
          <DashButton
            kind="gradient"
            small
            icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14"/></svg>}
          >
            Nouveau patient
          </DashButton>
        </Link>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{
          display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap',
        }}>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher UUID, ville, condition…"
            style={{
              flex: '1 1 280px', minWidth: 220,
              background: 'var(--s1)',
              border: '1px solid var(--line)',
              borderRadius: 10,
              padding: '9px 12px',
              color: 'var(--t1)',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <label style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            color: 'var(--t2)', fontSize: 12.5,
            fontFamily: 'var(--f-mono)', letterSpacing: '0.04em',
            textTransform: 'uppercase',
            userSelect: 'none', cursor: 'pointer',
          }}>
            <input
              type="checkbox"
              checked={onlyActive}
              onChange={(e) => setOnlyActive(e.target.checked)}
              style={{ accentColor: 'var(--accent)' }}
            />
            Actifs uniquement
          </label>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            style={{
              padding: '8px 12px', borderRadius: 8,
              background: 'var(--s1)', border: '1px solid var(--line)',
              color: 'var(--t1)', fontSize: 12.5, fontWeight: 600,
              cursor: isFetching ? 'wait' : 'pointer',
              opacity: isFetching ? 0.6 : 1,
            }}
          >
            {isFetching ? 'Sync…' : 'Rafraîchir'}
          </button>
        </div>

        {isLoading && (
          <div style={panelStyle}>
            <p style={{ margin: 0, color: 'var(--t2)', fontSize: 13.5 }}>Chargement…</p>
          </div>
        )}

        {isError && (
          <div style={{ ...panelStyle, borderColor: 'rgba(239,68,68,0.45)' }}>
            <p style={{ margin: 0, color: '#EF4444', fontSize: 13.5 }}>
              Impossible de charger la liste patients : {(error as Error)?.message ?? 'erreur inconnue'}.
            </p>
          </div>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div style={panelStyle}>
            <p style={{ margin: 0, color: 'var(--t2)', fontSize: 13.5 }}>
              Aucun patient ne correspond.
            </p>
          </div>
        )}

        {!isLoading && !isError && filtered.length > 0 && (
          <div style={{
            background: 'var(--s1)',
            border: '1px solid var(--line)',
            borderRadius: 14,
            overflow: 'hidden',
          }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{
                width: '100%', borderCollapse: 'collapse',
                fontSize: 13, color: 'var(--t1)',
              }}>
                <thead>
                  <tr style={{
                    background: 'var(--s2)',
                    borderBottom: '1px solid var(--line)',
                  }}>
                    {['UUID', 'Âge', 'Sexe', 'Ville', 'Conditions', 'Statut', 'Dernier RDV', 'Prochain RDV', ''].map((h) => (
                      <th key={h} style={thStyle}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr key={p.patient_uuid} style={{
                      borderBottom: '1px solid var(--line)',
                    }}>
                      <td style={{ ...tdStyle, fontFamily: 'var(--f-mono)', fontSize: 11.5 }}>
                        {shortUuid(p.patient_uuid)}
                      </td>
                      <td style={tdStyle}>{ageFrom(p.birth_year)}</td>
                      <td style={tdStyle}>{p.sex ?? '—'}</td>
                      <td style={{ ...tdStyle, fontFamily: 'var(--f-mono)' }}>{p.city_code ?? '—'}</td>
                      <td style={tdStyle}>
                        {p.chronic_conditions && p.chronic_conditions.length > 0
                          ? p.chronic_conditions.slice(0, 2).join(', ') +
                            (p.chronic_conditions.length > 2 ? '…' : '')
                          : <span style={{ color: 'var(--t3)' }}>aucune</span>}
                      </td>
                      <td style={tdStyle}>
                        {p.is_active
                          ? <StatusBadge tone="approved" label="actif" />
                          : <StatusBadge tone="rejected" label="effacé" />}
                      </td>
                      <td style={{ ...tdStyle, color: 'var(--t2)' }}>{formatDate(p.last_appointment_at)}</td>
                      <td style={{ ...tdStyle, color: 'var(--t2)' }}>{formatDate(p.next_appointment_at)}</td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>
                        <Link
                          href={`/patients/${p.patient_uuid}/dpa`}
                          style={{
                            display: 'inline-flex', alignItems: 'center',
                            padding: '6px 10px', borderRadius: 8,
                            background: 'var(--ai-grad)', color: '#fff',
                            fontSize: 11.5, fontWeight: 600, textDecoration: 'none',
                            letterSpacing: '0.04em',
                          }}
                        >
                          DPA →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data && data.total > filtered.length && (
              <div style={{
                padding: '10px 16px',
                borderTop: '1px solid var(--line)',
                color: 'var(--t3)', fontSize: 11.5,
                fontFamily: 'var(--f-mono)', letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}>
                {filtered.length} / {data.total} affichés · pagination ≥ {PAGE_SIZE} non encore implémentée
              </div>
            )}
          </div>
        )}
      </div>
    </DashPage>
  );
}

const panelStyle: React.CSSProperties = {
  background: 'var(--s1)',
  border: '1px solid var(--line)',
  borderRadius: 14,
  padding: 24,
};

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '10px 14px',
  fontSize: 10.5,
  fontFamily: 'var(--f-mono)',
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: 'var(--t3)',
  fontWeight: 600,
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '11px 14px',
  verticalAlign: 'middle',
};
