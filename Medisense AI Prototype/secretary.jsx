// Secretary screens: Agenda+feedback, CRM Tasks

const { DashboardLayout, DashButton, RiskPill, StatusPill } = window;
const SECRETARY_USER = { initial: 'L', name: 'Laila Bennis' };

const SECR_APPTS = [
  { time: '09:00', uid: 'a1b2c3d4', name: 'Ahmed Benali',     doctor: 'Dr. Merrouni', risk: 'danger', prob: 0.67, outcome: null },
  { time: '09:30', uid: 'e5f6g7h8', name: 'Salma Idrissi',    doctor: 'Dr. Merrouni', risk: 'safe',   prob: 0.08, outcome: 'completed' },
  { time: '10:00', uid: 'i9j0k1l2', name: 'Karim Ouahbi',     doctor: 'Dr. Bennis',   risk: 'warn',   prob: 0.34, outcome: 'no_show' },
  { time: '10:30', uid: 'm3n4o5p6', name: 'Fatima El Amrani', doctor: 'Dr. Merrouni', risk: 'safe',   prob: 0.12, outcome: 'completed' },
  { time: '11:00', uid: 'q7r8s9t0', name: 'Youssef Tazi',     doctor: 'Dr. Bennis',   risk: 'danger', prob: 0.71, outcome: null },
  { time: '11:30', uid: 'u1v2w3x4', name: 'Nadia Berrada',    doctor: 'Dr. Merrouni', risk: 'safe',   prob: 0.14, outcome: null },
];

function FeedbackPill({ outcome, onChange }) {
  if (outcome === 'completed') return <StatusPill tone="approved" label="Présenté"/>;
  if (outcome === 'no_show')   return <StatusPill tone="failed" label="Absent"/>;
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      <button onClick={() => onChange('completed')} style={{
        padding: '4px 9px', borderRadius: 99, cursor: 'pointer',
        background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.30)',
        color: '#22C55E', fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600, letterSpacing: '0.06em',
      }}>✓ présenté</button>
      <button onClick={() => onChange('no_show')} style={{
        padding: '4px 9px', borderRadius: 99, cursor: 'pointer',
        background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.30)',
        color: '#EF4444', fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600, letterSpacing: '0.06em',
      }}>✗ absent</button>
    </div>
  );
}

function SecretaryAgenda() {
  const [outcomes, setOutcomes] = React.useState(
    Object.fromEntries(SECR_APPTS.map(a => [a.uid, a.outcome]))
  );
  const dispatched = SECR_APPTS.filter(a => outcomes[a.uid] !== null).length;

  return (
    <DashboardLayout
      role="secretary" active="agenda" onChange={() => {}}
      user={SECRETARY_USER}
      breadcrumb="agenda · 10 mai 2026"
      title="Agenda — feedback ML"
      subtitle="Confirmation des résultats pour le re-entraînement du modèle no-show"
      actions={[
        <DashButton key="d" kind="solid" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18"/></svg>}>10 mai 2026</DashButton>,
        <DashButton key="b" kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12l5 5L20 7"/></svg>}>Soumettre lot ({dispatched}/{SECR_APPTS.length})</DashButton>,
      ]}
    >
      <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
        <div style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Total RDV jour</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600, color: 'var(--t0)', marginTop: 2 }}>{SECR_APPTS.length}</div>
        </div>
        <div style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Feedback fourni</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600, color: '#22C55E', marginTop: 2 }}>{dispatched}</div>
        </div>
        <div style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>En attente</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600, color: '#F59E0B', marginTop: 2 }}>{SECR_APPTS.length - dispatched}</div>
        </div>
        <div style={{ flex: 2, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Modèle XGBoost</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 4 }}>
            <span style={{ fontFamily: 'var(--f-display)', fontSize: 22, fontWeight: 600, color: 'var(--t0)' }}>v2.1</span>
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: '#22C55E' }}>AUC 0.847</span>
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t2)' }}>F1 0.79</span>
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)' }}>réentr. il y a 4h</span>
          </div>
        </div>
      </div>

      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '90px 1fr 160px 130px 1fr',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Heure</div>
          <div>Patient · médecin</div>
          <div>Prédit no-show</div>
          <div>Statut auto</div>
          <div>Résultat réel · feedback</div>
        </div>
        {SECR_APPTS.map((a, i) => (
          <div key={a.uid} style={{
            display: 'grid', gridTemplateColumns: '90px 1fr 160px 130px 1fr',
            padding: '13px 18px', alignItems: 'center',
            borderBottom: i < SECR_APPTS.length - 1 ? '1px solid var(--line)' : 'none',
          }}>
            <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 500, color: 'var(--t0)' }}>{a.time}</div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{a.name}</div>
              <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>{a.doctor} · <span style={{ fontFamily: 'var(--f-mono)', color: 'var(--t3)' }}>{a.uid}</span></div>
            </div>
            <div><RiskPill level={a.risk} prob={a.prob}/></div>
            <div>
              <StatusPill tone={a.risk === 'danger' ? 'failed' : a.risk === 'warn' ? 'pending' : 'sent'}
                label={a.risk === 'danger' ? 'À rappeler' : a.risk === 'warn' ? 'SMS envoyé' : 'Confirmé'}/>
            </div>
            <div><FeedbackPill outcome={outcomes[a.uid]} onChange={(v) => setOutcomes(o => ({ ...o, [a.uid]: v }))}/></div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 16, padding: '12px 16px',
        background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.30)',
        borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{ color: '#A78BFA' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
        </div>
        <div style={{ flex: 1, fontSize: 12.5, color: 'var(--t1)' }}>
          Chaque feedback alimente directement le ré-entraînement nocturne du modèle XGBoost. Les données sont anonymisées et soumises à <span style={{ fontFamily: 'var(--f-mono)', color: '#A78BFA' }}>POST /predict/feedback</span>.
        </div>
      </div>
    </DashboardLayout>
  );
}

// ───────────────── CRM Tasks ─────────────────
const CRM_TASKS = [
  { uid: 'a1b2c3d4', name: 'Ahmed Benali', time: '09:00', status: 'sent',    error: null,                  attempts: 1, sf: 'A-2814' },
  { uid: 'e5f6g7h8', name: 'Salma Idrissi', time: '09:30', status: 'sent',    error: null,                  attempts: 1, sf: 'A-2815' },
  { uid: 'i9j0k1l2', name: 'Karim Ouahbi',  time: '10:00', status: 'failed',  error: 'Timeout (30s)',       attempts: 3, sf: null },
  { uid: 'm3n4o5p6', name: 'Fatima El Amrani', time: '10:30', status: 'pending', error: null,               attempts: 0, sf: null },
  { uid: 'q7r8s9t0', name: 'Youssef Tazi',  time: '11:00', status: 'cb',      error: 'Circuit breaker open',attempts: 5, sf: null },
  { uid: 'u1v2w3x4', name: 'Nadia Berrada', time: '11:30', status: 'sent',    error: null,                  attempts: 1, sf: 'A-2818' },
  { uid: 'y5z6a7b8', name: 'Hamza Saidi',   time: '14:00', status: 'skipped', error: 'consent OFF (NLP)',   attempts: 0, sf: null },
  { uid: 'c9d0e1f2', name: 'Imane Lahlou',  time: '14:30', status: 'pending', error: null,                  attempts: 0, sf: null },
];

const CRM_LABELS = {
  pending: 'En attente',
  sent:    'Synchronisé',
  failed:  'Échec',
  skipped: 'Ignoré',
  cb:      'Circuit ouvert',
};

function SecretaryCrm() {
  const [filter, setFilter] = React.useState('all');
  const [tasks, setTasks] = React.useState(CRM_TASKS);

  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);
  const counts = tasks.reduce((acc, t) => { acc[t.status] = (acc[t.status] || 0) + 1; return acc; }, {});

  const retry = (uid) => {
    setTasks(prev => prev.map(t => t.uid === uid ? { ...t, status: 'pending', attempts: t.attempts + 1, error: null } : t));
  };

  return (
    <DashboardLayout
      role="secretary" active="crm" onChange={() => {}}
      user={SECRETARY_USER}
      breadcrumb="intégrations · salesforce"
      title="Tâches CRM Salesforce"
      subtitle="Synchronisation automatique des RDV · Sprint 6 · circuit breaker actif"
      actions={[
        <DashButton key="r" kind="solid" small icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5"/></svg>}>Actualiser</DashButton>,
        <DashButton key="e" kind="gradient" small>Exporter CSV</DashButton>,
      ]}
    >
      {/* status row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        {[
          { key: 'all',     label: 'Tous',    count: tasks.length, tone: 'info' },
          { key: 'sent',    label: 'Envoyés', count: counts.sent || 0, tone: 'sent' },
          { key: 'pending', label: 'En attente', count: counts.pending || 0, tone: 'pending' },
          { key: 'failed',  label: 'Échecs', count: counts.failed || 0, tone: 'failed' },
          { key: 'cb',      label: 'CB ouverts', count: counts.cb || 0, tone: 'cb' },
          { key: 'skipped', label: 'Ignorés', count: counts.skipped || 0, tone: 'skipped' },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)} style={{
            padding: '8px 14px', borderRadius: 99, cursor: 'pointer',
            background: filter === f.key ? 'var(--ai-grad-soft)' : 'var(--s1)',
            border: `1px solid ${filter === f.key ? 'rgba(139,92,246,0.55)' : 'var(--line)'}`,
            color: 'var(--t0)', fontFamily: 'var(--f-body)', fontSize: 12,
            display: 'inline-flex', alignItems: 'center', gap: 8,
          }}>
            <span>{f.label}</span>
            <span style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
              color: 'var(--t1)',
              background: 'var(--s2)', padding: '1px 7px', borderRadius: 99,
            }}>{f.count}</span>
          </button>
        ))}
      </div>

      {/* circuit breaker banner */}
      {counts.cb > 0 && (
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
            <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 600 }}>Circuit breaker ouvert · API Salesforce</div>
            <div style={{ fontSize: 12, color: 'var(--t2)', marginTop: 2 }}>
              Re-fermeture automatique dans <span style={{ fontFamily: 'var(--f-mono)', color: '#F43F5E' }}>02:14</span> · taux d'erreur 87% sur 5 min
            </div>
          </div>
          <DashButton kind="solid" small>Forcer la fermeture</DashButton>
        </div>
      )}

      {/* table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '70px 1fr 1fr 120px 1fr 90px 110px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
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
        {filtered.map((t, i) => (
          <div key={t.uid} style={{
            display: 'grid', gridTemplateColumns: '70px 1fr 1fr 120px 1fr 90px 110px',
            padding: '13px 18px', alignItems: 'center',
            borderBottom: i < filtered.length - 1 ? '1px solid var(--line)' : 'none',
          }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>{t.time}</div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{t.name}</div>
              <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>uid · {t.uid}</div>
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: t.sf ? 'var(--t1)' : 'var(--t4)' }}>
              {t.sf ? `sf · ${t.sf}` : '— '}
            </div>
            <div>
              <StatusPill
                tone={t.status}
                label={CRM_LABELS[t.status]}
                pulse={t.status === 'pending' || t.status === 'cb'}
              />
            </div>
            <div style={{ fontSize: 11.5, color: t.error ? '#FCA5A5' : 'var(--t4)', fontFamily: t.error ? 'var(--f-mono)' : 'inherit' }}>
              {t.error || '—'}
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: t.attempts >= 3 ? '#F59E0B' : 'var(--t2)' }}>
              {t.attempts}/5
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              {(t.status === 'failed' || t.status === 'cb') && (
                <button onClick={() => retry(t.uid)} style={{
                  padding: '5px 10px', borderRadius: 6, cursor: 'pointer',
                  background: 'var(--ai-grad-soft)', border: '1px solid rgba(139,92,246,0.40)',
                  color: '#C4B5FD', fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                  letterSpacing: '0.08em', textTransform: 'uppercase',
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M3 12a9 9 0 0115-6.7L21 8"/></svg>
                  Retry
                </button>
              )}
              {t.status === 'pending' && (
                <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>en file…</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}

Object.assign(window, { SecretaryAgenda, SecretaryCrm });
