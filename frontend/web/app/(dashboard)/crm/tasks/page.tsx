'use client';
import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { StatusBadge } from '@/components/status-badge';
import { DashButton } from '@/components/dash-button';
import { DashPage } from '@/components/dashboard-shell';
import { IconSync } from '@/components/icons';

type TaskStatus = 'PENDING' | 'SENT' | 'FAILED' | 'SKIPPED' | 'CB_OPEN';

interface CRMTask {
  uuid: string;
  patient_uuid: string;
  patient_name: string;
  scheduled_at: string;
  status: TaskStatus;
  error_message?: string;
  retry_count: number;
  salesforce_id?: string | null;
}

interface TasksResponse {
  tasks: CRMTask[];
  total: number;
  cb_open: boolean;
  cb_reopens_in?: number;
}

type FilterKey = 'all' | 'sent' | 'pending' | 'failed' | 'cb' | 'skipped';

const STATUS_TONE_MAP: Record<TaskStatus, 'pending' | 'sent' | 'failed' | 'skipped' | 'cb'> = {
  PENDING: 'pending',
  SENT: 'sent',
  FAILED: 'failed',
  SKIPPED: 'skipped',
  CB_OPEN: 'cb',
};

const STATUS_LABEL: Record<TaskStatus, string> = {
  PENDING: 'En attente',
  SENT: 'Synchronisé',
  FAILED: 'Échec',
  SKIPPED: 'Ignoré',
  CB_OPEN: 'Circuit ouvert',
};

const FILTER_TO_STATUS: Record<Exclude<FilterKey, 'all'>, TaskStatus> = {
  sent: 'SENT',
  pending: 'PENDING',
  failed: 'FAILED',
  cb: 'CB_OPEN',
  skipped: 'SKIPPED',
};

function formatCountdown(s: number): string {
  const m = Math.floor(s / 60).toString().padStart(2, '0');
  const r = Math.floor(s % 60).toString().padStart(2, '0');
  return `${m}:${r}`;
}

export default function CRMTasksPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<FilterKey>('all');
  const [toast, setToast] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number>(0);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const { data, isLoading, isError } = useQuery<TasksResponse>({
    queryKey: ['crm-tasks'],
    queryFn: async () => {
      const { data } = await api.get('/crm/tasks');
      return data;
    },
    refetchInterval: 15000,
  });

  const retryMutation = useMutation({
    mutationFn: async (taskUuid: string) => {
      const { data } = await api.post(`/crm/tasks/${taskUuid}/retry`);
      return data;
    },
    onSuccess: () => {
      showToast('Tâche relancée');
      queryClient.invalidateQueries({ queryKey: ['crm-tasks'] });
    },
    onError: () => showToast('Échec de la relance'),
  });

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (data?.cb_reopens_in) setCountdown(data.cb_reopens_in);
  }, [data?.cb_reopens_in]);

  useEffect(() => {
    if (countdown <= 0) return;
    const id = setInterval(() => setCountdown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [countdown]);

  const tasks = data?.tasks ?? [];
  const filtered = filter === 'all' ? tasks : tasks.filter((t) => t.status === FILTER_TO_STATUS[filter]);

  const countBy = (s: TaskStatus | 'all') =>
    s === 'all' ? tasks.length : tasks.filter((t) => t.status === s).length;

  const filters: { key: FilterKey; label: string; count: number }[] = [
    { key: 'all',     label: 'Tous',       count: countBy('all') },
    { key: 'sent',    label: 'Envoyés',    count: countBy('SENT') },
    { key: 'pending', label: 'En attente', count: countBy('PENDING') },
    { key: 'failed',  label: 'Échecs',     count: countBy('FAILED') },
    { key: 'cb',      label: 'CB ouverts', count: countBy('CB_OPEN') },
    { key: 'skipped', label: 'Ignorés',    count: countBy('SKIPPED') },
  ];

  const cbOpen = (data?.cb_open ?? false) || countBy('CB_OPEN') > 0;

  return (
    <>
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 24, zIndex: 9999,
          background: 'var(--s2)', border: '1px solid var(--line-strong)',
          borderRadius: 10, padding: '10px 18px',
          color: 'var(--t0)', fontSize: 13, fontWeight: 500,
          animation: 'slide-down 0.2s ease',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}>
          {toast}
        </div>
      )}

      <DashPage
        breadcrumb="intégrations · salesforce"
        title="Tâches CRM Salesforce"
        subtitle="Synchronisation automatique des RDV · Sprint 6 · circuit breaker actif"
        actions={
          <>
            <DashButton
              kind="solid"
              small
              icon={<IconSync size={13} />}
              onClick={() => queryClient.invalidateQueries({ queryKey: ['crm-tasks'] })}
            >
              Actualiser
            </DashButton>
            <DashButton kind="gradient" small>Exporter CSV</DashButton>
          </>
        }
      >
        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          {filters.map((f) => {
            const isActive = filter === f.key;
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                style={{
                  padding: '8px 14px', borderRadius: 99, cursor: 'pointer',
                  background: isActive ? 'var(--ai-grad-soft)' : 'var(--s1)',
                  border: `1px solid ${isActive ? 'rgba(139,92,246,0.55)' : 'var(--line)'}`,
                  color: 'var(--t0)', fontFamily: 'var(--f-body)', fontSize: 12,
                  display: 'inline-flex', alignItems: 'center', gap: 8,
                }}
              >
                <span>{f.label}</span>
                <span style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                  color: 'var(--t1)',
                  background: 'var(--s2)', padding: '1px 7px', borderRadius: 99,
                }}>
                  {f.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Circuit breaker banner */}
        {cbOpen && (
          <div style={{
            padding: '12px 16px', borderRadius: 12,
            background: 'linear-gradient(135deg, rgba(244,63,94,0.10), rgba(244,63,94,0.04))',
            border: '1px solid rgba(244,63,94,0.40)',
            marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 14,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: 'rgba(244,63,94,0.18)', border: '1px solid rgba(244,63,94,0.40)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#F43F5E',
            }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 600 }}>
                Circuit breaker ouvert · API Salesforce
              </div>
              <div style={{ fontSize: 12, color: 'var(--t2)', marginTop: 2 }}>
                {countdown > 0 ? (
                  <>Re-fermeture automatique dans <span style={{ fontFamily: 'var(--f-mono)', color: '#F43F5E' }}>{formatCountdown(countdown)}</span></>
                ) : (
                  <>Trop d&apos;erreurs consécutives — les envois SMS sont suspendus. Retry manuel requis.</>
                )}
              </div>
            </div>
            <DashButton kind="solid" small>Forcer la fermeture</DashButton>
          </div>
        )}

        {/* Table */}
        <div style={{
          background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
        }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '70px 1fr 1fr 120px 1fr 90px 110px',
            padding: '11px 18px', background: 'var(--s2)',
            fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
            letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 500,
            borderBottom: '1px solid var(--line)',
          }}>
            <div>RDV</div>
            <div>Patient</div>
            <div>Salesforce ID</div>
            <div>Statut</div>
            <div>Erreur</div>
            <div>Tentatives</div>
            <div></div>
          </div>

          {isLoading && Array.from({ length: 5 }).map((_, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '70px 1fr 1fr 120px 1fr 90px 110px',
              padding: '13px 18px', alignItems: 'center',
              borderBottom: '1px solid var(--line)',
            }}>
              {[60, 140, 100, 90, 160, 50, 80].map((w, j) => (
                <div key={j} style={{
                  height: 12, width: w, borderRadius: 4,
                  background: 'linear-gradient(90deg, var(--s2) 25%, var(--s3) 50%, var(--s2) 75%)',
                  backgroundSize: '400px 100%', animation: 'shimmer 1.5s infinite',
                }} />
              ))}
            </div>
          ))}

          {!isLoading && isError && (
            <div style={{ padding: 40, textAlign: 'center', color: '#EF4444', fontSize: 13 }}>
              Erreur de chargement des tâches CRM.
            </div>
          )}

          {!isLoading && !isError && filtered.length === 0 && (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
              Aucune tâche dans cette catégorie
            </div>
          )}

          {!isLoading && filtered.map((t, i) => {
            const date = new Date(t.scheduled_at);
            const timeStr = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
            const canRetry = t.status === 'FAILED' || t.status === 'CB_OPEN';
            const isRetrying = retryMutation.isPending && retryMutation.variables === t.uuid;
            return (
              <div key={t.uuid} style={{
                display: 'grid', gridTemplateColumns: '70px 1fr 1fr 120px 1fr 90px 110px',
                padding: '13px 18px', alignItems: 'center',
                borderBottom: i < filtered.length - 1 ? '1px solid var(--line)' : 'none',
                transition: 'background 0.12s',
              }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(99,102,241,0.04)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>{timeStr}</div>
                <div>
                  <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{t.patient_name}</div>
                  <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>
                    uid · {t.patient_uuid.slice(0, 8)}
                  </div>
                </div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 11,
                  color: t.salesforce_id ? 'var(--t1)' : 'var(--t4)',
                }}>
                  {t.salesforce_id ? `sf · ${t.salesforce_id}` : '— '}
                </div>
                <div>
                  <StatusBadge
                    tone={STATUS_TONE_MAP[t.status]}
                    label={STATUS_LABEL[t.status]}
                    pulse={t.status === 'PENDING' || t.status === 'CB_OPEN'}
                  />
                </div>
                <div style={{
                  fontSize: 11.5,
                  color: t.error_message ? '#FCA5A5' : 'var(--t4)',
                  fontFamily: t.error_message ? 'var(--f-mono)' : 'inherit',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {t.error_message || '—'}
                </div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 11,
                  color: t.retry_count >= 3 ? '#F59E0B' : 'var(--t2)',
                }}>
                  {t.retry_count}/5
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  {canRetry && (
                    <button
                      onClick={() => retryMutation.mutate(t.uuid)}
                      disabled={isRetrying}
                      style={{
                        padding: '5px 10px', borderRadius: 6,
                        cursor: isRetrying ? 'default' : 'pointer',
                        background: 'var(--ai-grad-soft)', border: '1px solid rgba(139,92,246,0.40)',
                        color: '#C4B5FD', fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                        letterSpacing: '0.08em', textTransform: 'uppercase',
                        display: 'inline-flex', alignItems: 'center', gap: 5,
                        opacity: isRetrying ? 0.6 : 1,
                      }}
                    >
                      {isRetrying ? (
                        <span style={{
                          width: 10, height: 10,
                          border: '1.5px solid rgba(196,181,253,0.3)',
                          borderTopColor: '#C4B5FD',
                          borderRadius: '50%',
                          animation: 'spin 0.8s linear infinite',
                        }} />
                      ) : (
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M3 12a9 9 0 0115-6.7L21 8"/></svg>
                      )}
                      Retry
                    </button>
                  )}
                  {t.status === 'PENDING' && (
                    <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>en file…</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div style={{ marginTop: 14, fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t4)' }}>
          Total : {data?.total ?? 0} tâches · actualisation auto toutes les 15 s
        </div>
      </DashPage>
    </>
  );
}
