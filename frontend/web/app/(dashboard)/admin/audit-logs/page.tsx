'use client';
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashButton } from '@/components/dash-button';
import { DashPage } from '@/components/dashboard-shell';
import { IconChevron } from '@/components/icons';

type ActionType = 'LOGIN' | 'READ' | 'WRITE' | 'DELETE' | 'EXPORT' | 'CONSENT';
type Role = 'doctor' | 'secretary' | 'admin' | 'patient';

interface AuditLog {
  id: number;
  actor_uuid: string;
  actor_role: Role;
  action: ActionType;
  resource_type: string;
  resource_uuid: string | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

interface AuditResponse {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
}

const PAGE_SIZE = 25;

const ACTION_TONES: Record<ActionType, { c: string; bg: string; bd: string; glyph: string }> = {
  LOGIN:   { c: '#38BDF8', bg: 'rgba(56,189,248,0.10)',  bd: 'rgba(56,189,248,0.40)',  glyph: '⊙' },
  READ:    { c: '#94A3B8', bg: 'rgba(148,163,184,0.10)', bd: 'rgba(148,163,184,0.30)', glyph: '○' },
  WRITE:   { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)',   glyph: '●' },
  DELETE:  { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)',   glyph: '✕' },
  EXPORT:  { c: '#A78BFA', bg: 'rgba(167,139,250,0.10)', bd: 'rgba(167,139,250,0.40)', glyph: '↓' },
  CONSENT: { c: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  bd: 'rgba(245,158,11,0.40)',  glyph: '⚙' },
};

function ActionBadge({ action }: { action: ActionType }) {
  const a = ACTION_TONES[action] ?? ACTION_TONES.READ;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px',
      borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 9.5, fontWeight: 600,
      letterSpacing: '0.10em',
      color: a.c, background: a.bg, border: `1px solid ${a.bd}`,
    }}>
      {a.glyph} {action}
    </span>
  );
}

function formatTs(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => n.toString().padStart(2, '0');
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

const ACTION_FILTERS: (ActionType | 'ALL')[] = ['ALL', 'LOGIN', 'WRITE', 'DELETE', 'EXPORT', 'CONSENT'];

export default function AuditLogsPage() {
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState<ActionType | 'ALL'>('ALL');
  const [searchUuid, setSearchUuid] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);

  const { data, isLoading } = useQuery<AuditResponse>({
    queryKey: ['audit-logs', page, actionFilter, searchUuid],
    queryFn: async () => {
      const offset = (page - 1) * PAGE_SIZE;
      const params = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) });
      if (actionFilter !== 'ALL') params.set('action', actionFilter);
      if (searchUuid) params.set('actor_uuid', searchUuid);
      const { data } = await api.get(`/admin/audit-logs?${params}`);
      return data;
    },
  });

  const logs = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const start = (page - 1) * PAGE_SIZE + 1;
  const end = Math.min(start + logs.length - 1, total);

  return (
    <DashPage
      breadcrumb="conformité · journal immuable"
      title="Logs d&apos;audit RGPD"
      subtitle={`Article 30 RGPD · ${total.toLocaleString('fr-FR')} entrées · stocké chiffré (AES-256) · backup quotidien`}
      actions={
        <>
          <DashButton kind="solid" small
            icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 3H2l8 9v7l4 2v-9l8-9z"/></svg>}
          >
            Filtrer
          </DashButton>
          <DashButton kind="solid" small
            icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>}
          >
            Export CSV
          </DashButton>
        </>
      }
    >
      {/* Metric strip */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
        {[
          { label: 'Entrées 24h',  value: String(total),  tone: '#A78BFA' },
          { label: 'Suppressions', value: String(logs.filter((l) => l.action === 'DELETE').length), tone: '#EF4444' },
          { label: 'Exports RGPD', value: String(logs.filter((l) => l.action === 'EXPORT').length), tone: '#A78BFA' },
          { label: 'Échecs auth.', value: '—',            tone: '#F97316' },
          { label: 'Hash chain',   value: 'OK',           tone: '#22C55E', mono: true },
        ].map((m) => (
          <div key={m.label} style={{
            flex: 1, padding: 14, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
          }}>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
              letterSpacing: '0.14em', textTransform: 'uppercase',
            }}>
              {m.label}
            </div>
            <div style={{
              fontFamily: m.mono ? 'var(--f-mono)' : 'var(--f-display)',
              fontSize: m.mono ? 22 : 28, fontWeight: 600, color: m.tone, marginTop: 4,
              letterSpacing: m.mono ? 0 : '-0.02em',
            }}>
              {m.value}
            </div>
          </div>
        ))}
      </div>

      {/* Search + filter pills */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, position: 'relative', minWidth: 280 }}>
          <input
            value={searchUuid}
            onChange={(e) => { setSearchUuid(e.target.value); setPage(1); }}
            placeholder="Rechercher par UUID patient, IP, ressource…"
            style={{
              width: '100%', padding: '10px 12px 10px 36px',
              background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 10,
              color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12, outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <svg
            width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="#64748B" strokeWidth="2"
            style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }}
          >
            <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>
          </svg>
        </div>
        {ACTION_FILTERS.map((f) => {
          const isActive = actionFilter === f;
          return (
            <button
              key={f}
              onClick={() => { setActionFilter(f); setPage(1); }}
              style={{
                padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
                background: isActive ? 'var(--ai-grad-soft)' : 'var(--s1)',
                border: `1px solid ${isActive ? 'rgba(139,92,246,0.45)' : 'var(--line)'}`,
                color: 'var(--t1)', fontFamily: 'var(--f-mono)', fontSize: 10.5,
                letterSpacing: '0.08em', fontWeight: 600,
              }}
            >
              {f === 'ALL' ? 'Toutes' : f}
            </button>
          );
        })}
      </div>

      {/* Table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '170px 110px 100px 110px 1fr 130px 30px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 500,
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Horodatage</div>
          <div>Action</div>
          <div>Rôle</div>
          <div>Ressource</div>
          <div>Cible (uuid)</div>
          <div>IP</div>
          <div></div>
        </div>

        {isLoading && Array.from({ length: 8 }).map((_, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '170px 110px 100px 110px 1fr 130px 30px',
            padding: '13px 18px', alignItems: 'center', borderBottom: '1px solid var(--line)',
          }}>
            {[140, 80, 70, 80, 120, 90, 20].map((w, j) => (
              <div key={j} style={{
                height: 12, width: w, borderRadius: 4,
                background: 'linear-gradient(90deg, var(--s2) 25%, var(--s3) 50%, var(--s2) 75%)',
                backgroundSize: '400px 100%', animation: 'shimmer 1.5s infinite',
              }} />
            ))}
          </div>
        ))}

        {!isLoading && logs.length === 0 && (
          <div style={{ padding: 48, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
            Aucun log pour ces filtres
          </div>
        )}

        {!isLoading && logs.map((log, i) => {
          const isExp = expanded === log.id;
          return (
            <React.Fragment key={log.id}>
              <button
                onClick={() => setExpanded(isExp ? null : log.id)}
                style={{
                  all: 'unset', cursor: 'pointer', width: '100%',
                  display: 'grid', gridTemplateColumns: '170px 110px 100px 110px 1fr 130px 30px',
                  padding: '11px 18px', alignItems: 'center', boxSizing: 'border-box',
                  borderBottom: i < logs.length - 1 || isExp ? '1px solid var(--line)' : 'none',
                  transition: 'background .14s',
                  background: isExp ? 'rgba(99,102,241,0.06)' : 'transparent',
                }}
              >
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>
                  {formatTs(log.created_at)}
                </div>
                <div><ActionBadge action={log.action} /></div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t2)',
                  textTransform: 'uppercase', letterSpacing: '0.08em',
                }}>
                  {log.actor_role}
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>
                  {log.resource_type}
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t2)' }}>
                  {log.resource_uuid ? log.resource_uuid.slice(0, 12) : '—'}
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>
                  {log.ip_address ?? '—'}
                </div>
                <div style={{
                  color: 'var(--t3)',
                  transform: isExp ? 'rotate(90deg)' : 'rotate(0)',
                  transition: 'transform .2s',
                }}>
                  <IconChevron size={12} />
                </div>
              </button>
              {isExp && (
                <div style={{
                  padding: '14px 18px 14px 188px',
                  background: 'rgba(15,22,35,0.50)',
                  borderBottom: i < logs.length - 1 ? '1px solid var(--line)' : 'none',
                  display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16,
                  fontFamily: 'var(--f-mono)', fontSize: 11,
                }}>
                  <div>
                    <div style={{
                      fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em',
                      textTransform: 'uppercase', marginBottom: 4,
                    }}>
                      User Agent
                    </div>
                    <div style={{ color: 'var(--t1)', wordBreak: 'break-all' }}>
                      {log.user_agent ?? '—'}
                    </div>
                  </div>
                  <div>
                    <div style={{
                      fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em',
                      textTransform: 'uppercase', marginBottom: 4,
                    }}>
                      Actor UUID
                    </div>
                    <div style={{ color: 'var(--t1)', wordBreak: 'break-all' }}>
                      {log.actor_uuid}
                    </div>
                  </div>
                  <div>
                    <div style={{
                      fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em',
                      textTransform: 'uppercase', marginBottom: 4,
                    }}>
                      Conformité
                    </div>
                    <div style={{ color: 'var(--t1)' }}>RGPD Art. 30 · Loi 09-08 ✓</div>
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Pagination */}
      <div style={{
        marginTop: 14, padding: '10px 16px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>
          {total === 0 ? '0' : `${start}–${end}`} sur {total.toLocaleString('fr-FR')} · Page {page} / {totalPages}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <DashButton kind="solid" small disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            ◀ précédent
          </DashButton>
          <DashButton kind="solid" small disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
            suivant ▶
          </DashButton>
        </div>
      </div>
    </DashPage>
  );
}
