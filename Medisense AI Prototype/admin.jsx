// Admin screens: Audit Logs (RGPD), Users, Rerank Eval

const { DashboardLayout, DashButton, StatusPill } = window;
const ADMIN_USER = { initial: 'A', name: 'admin@medisense.ai' };

// ───────────────── Audit Logs ─────────────────
const AUDIT_LOGS = [
  { ts: '10/05 14:32:18', action: 'LOGIN',   role: 'admin',     resource: 'user',    target: 'a1b2c3d4', ip: '127.0.0.1',  ua: 'Chrome 124 · macOS' },
  { ts: '10/05 14:31:02', action: 'EXPORT',  role: 'admin',     resource: 'patient', target: 'e5f6g7h8', ip: '127.0.0.1',  ua: 'Chrome 124 · macOS' },
  { ts: '10/05 14:28:44', action: 'WRITE',   role: 'doctor',    resource: 'dpa',     target: 'q7r8s9t0', ip: '10.0.2.18',  ua: 'Edge 119 · Windows' },
  { ts: '10/05 14:21:09', action: 'READ',    role: 'doctor',    resource: 'patient', target: 'a1b2c3d4', ip: '10.0.2.18',  ua: 'Edge 119 · Windows' },
  { ts: '10/05 13:54:30', action: 'CONSENT', role: 'patient',   resource: 'consent', target: 'm3n4o5p6', ip: '105.66.4.81', ua: 'Flutter Mobile · iOS 17' },
  { ts: '10/05 13:42:11', action: 'DELETE',  role: 'admin',     resource: 'patient', target: 'z9y8x7w6', ip: '127.0.0.1',  ua: 'Chrome 124 · macOS' },
  { ts: '10/05 13:38:55', action: 'WRITE',   role: 'secretary', resource: 'feedback',target: 'i9j0k1l2', ip: '10.0.2.04',  ua: 'Firefox 122 · Windows' },
  { ts: '10/05 13:12:00', action: 'LOGIN',   role: 'doctor',    resource: 'user',    target: 'doctor-merrouni', ip: '10.0.2.18', ua: 'Edge 119 · Windows' },
  { ts: '10/05 12:48:22', action: 'READ',    role: 'patient',   resource: 'iot',     target: 'a1b2c3d4', ip: '105.66.4.81', ua: 'Flutter Mobile · iOS 17' },
  { ts: '10/05 12:31:14', action: 'EXPORT',  role: 'patient',   resource: 'data',    target: 'a1b2c3d4', ip: '105.66.4.81', ua: 'Flutter Mobile · iOS 17' },
  { ts: '10/05 11:55:08', action: 'CONSENT', role: 'patient',   resource: 'consent', target: 'e5f6g7h8', ip: '105.66.4.92', ua: 'Flutter Mobile · Android 14' },
];

const ACTION_TONES = {
  LOGIN:   { c: '#38BDF8', bg: 'rgba(56,189,248,0.10)',  bd: 'rgba(56,189,248,0.40)',  glyph: '⊙' },
  READ:    { c: '#94A3B8', bg: 'rgba(148,163,184,0.10)', bd: 'rgba(148,163,184,0.30)', glyph: '○' },
  WRITE:   { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)',   glyph: '●' },
  DELETE:  { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)',   glyph: '✕' },
  EXPORT:  { c: '#A78BFA', bg: 'rgba(167,139,250,0.10)', bd: 'rgba(167,139,250,0.40)', glyph: '↓' },
  CONSENT: { c: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  bd: 'rgba(245,158,11,0.40)',  glyph: '⚙' },
};

function ActionBadge({ action }) {
  const a = ACTION_TONES[action];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '2px 8px',
      borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 9.5, fontWeight: 600,
      letterSpacing: '0.10em',
      color: a.c, background: a.bg, border: `1px solid ${a.bd}`,
    }}>{a.glyph} {action}</span>
  );
}

function AdminAudit() {
  const [expanded, setExpanded] = React.useState(null);
  return (
    <DashboardLayout
      role="admin" active="audit" onChange={() => {}}
      user={ADMIN_USER}
      breadcrumb="conformité · journal immuable"
      title="Logs d'audit RGPD"
      subtitle="Article 30 RGPD · 4 821 entrées · stocké chiffré (AES-256) · backup quotidien"
      actions={[
        <DashButton key="f" kind="solid" small icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 3H2l8 9v7l4 2v-9l8-9z"/></svg>}>Filtrer</DashButton>,
        <DashButton key="e" kind="solid" small icon={<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>}>Export CSV</DashButton>,
      ]}
    >
      {/* metric strip */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
        {[
          { label: 'Entrées 24h', value: '342', tone: '#A78BFA' },
          { label: 'Suppressions', value: '3',   tone: '#EF4444' },
          { label: 'Exports RGPD', value: '12',  tone: '#A78BFA' },
          { label: 'Échecs auth.',  value: '7',   tone: '#F97316' },
          { label: 'Hash chain',   value: 'OK',  tone: '#22C55E', mono: true },
        ].map(m => (
          <div key={m.label} style={{ flex: 1, padding: 14, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{m.label}</div>
            <div style={{
              fontFamily: m.mono ? 'var(--f-mono)' : 'var(--f-display)',
              fontSize: m.mono ? 22 : 28, fontWeight: 600, color: m.tone, marginTop: 4,
              letterSpacing: m.mono ? 0 : '-0.02em',
            }}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* search */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <input
            placeholder="Rechercher par UUID patient, IP, ressource…"
            style={{
              width: '100%', padding: '10px 12px 10px 36px',
              background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 10,
              color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12, outline: 'none',
            }}
          />
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }}>
            <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>
          </svg>
        </div>
        {['Toutes', 'LOGIN', 'WRITE', 'DELETE', 'EXPORT', 'CONSENT'].map((f, i) => (
          <button key={f} style={{
            padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
            background: i === 0 ? 'var(--ai-grad-soft)' : 'var(--s1)',
            border: `1px solid ${i === 0 ? 'rgba(139,92,246,0.45)' : 'var(--line)'}`,
            color: 'var(--t1)', fontFamily: 'var(--f-mono)', fontSize: 10.5,
            letterSpacing: '0.08em', fontWeight: 600,
          }}>{f}</button>
        ))}
      </div>

      {/* table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '170px 110px 100px 110px 1fr 130px 30px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
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
        {AUDIT_LOGS.map((l, i) => {
          const isExp = expanded === i;
          return (
            <React.Fragment key={i}>
              <button onClick={() => setExpanded(isExp ? null : i)} style={{
                all: 'unset', cursor: 'pointer', width: '100%',
                display: 'grid', gridTemplateColumns: '170px 110px 100px 110px 1fr 130px 30px',
                padding: '11px 18px', alignItems: 'center',
                borderBottom: '1px solid var(--line)',
                transition: 'background .14s',
                background: isExp ? 'rgba(99,102,241,0.06)' : 'transparent',
              }}>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>{l.ts}</div>
                <div><ActionBadge action={l.action}/></div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t2)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{l.role}</div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)' }}>{l.resource}</div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t2)' }}>{l.target}</div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>{l.ip}</div>
                <div style={{ color: 'var(--t3)', transform: isExp ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform .2s' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 6l6 6-6 6"/></svg>
                </div>
              </button>
              {isExp && (
                <div style={{
                  padding: '14px 18px 14px 188px', background: 'rgba(15,22,35,0.50)',
                  borderBottom: '1px solid var(--line)',
                  display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16,
                  fontFamily: 'var(--f-mono)', fontSize: 11,
                }}>
                  <div>
                    <div style={{ fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>User Agent</div>
                    <div style={{ color: 'var(--t1)' }}>{l.ua}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>Hash chain</div>
                    <div style={{ color: '#22C55E' }}>0x7f3a · linked ✓</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>Conformité</div>
                    <div style={{ color: 'var(--t1)' }}>RGPD Art. 30 · Loi 09-08 ✓</div>
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* pagination */}
      <div style={{
        marginTop: 14, padding: '10px 16px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>
          1–11 sur 4 821 · Page 1 / 439
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <DashButton kind="solid" small>◀ précédent</DashButton>
          <DashButton kind="solid" small>suivant ▶</DashButton>
        </div>
      </div>
    </DashboardLayout>
  );
}

// ───────────────── Users ─────────────────
const USERS = [
  { email: 'admin@medisense.ai',     role: 'admin',     active: true,  last: '14:32 aujourd\'hui',     mfa: true },
  { email: 'dr.merrouni@clinique.ma',role: 'doctor',    active: true,  last: '14:21 aujourd\'hui',     mfa: true },
  { email: 'dr.bennis@clinique.ma',  role: 'doctor',    active: true,  last: 'hier · 18:42',           mfa: true },
  { email: 'l.bennis@clinique.ma',   role: 'secretary', active: true,  last: '13:38 aujourd\'hui',     mfa: false },
  { email: 'a.benali@email.ma',      role: 'patient',   active: true,  last: '13:42 aujourd\'hui',     mfa: false },
  { email: 's.idrissi@email.ma',     role: 'patient',   active: true,  last: '8 mai · 09:12',          mfa: false },
  { email: 'old.account@clinique.ma',role: 'doctor',    active: false, last: 'il y a 4 mois',          mfa: false },
];

function AdminUsers() {
  const [showCreate, setShowCreate] = React.useState(false);
  return (
    <DashboardLayout
      role="admin" active="users" onChange={() => {}}
      user={ADMIN_USER}
      breadcrumb="comptes · gestion"
      title="Gestion des utilisateurs"
      subtitle="Création, désactivation, MFA · 7 comptes au total"
      actions={[
        <DashButton key="i" kind="solid" small>Inviter par email</DashButton>,
        <DashButton key="c" kind="gradient" small onClick={() => setShowCreate(true)} icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 5v14M5 12h14"/></svg>}>Créer un compte</DashButton>,
      ]}
    >
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '40px 1.5fr 110px 90px 80px 1fr 60px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
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
        {USERS.map((u, i) => (
          <div key={u.email} style={{
            display: 'grid', gridTemplateColumns: '40px 1.5fr 110px 90px 80px 1fr 60px',
            padding: '13px 18px', alignItems: 'center',
            borderBottom: i < USERS.length - 1 ? '1px solid var(--line)' : 'none',
            opacity: u.active ? 1 : 0.55,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 99,
              background: u.role === 'admin' ? 'var(--ai-grad)' : u.role === 'doctor' ? 'rgba(56,189,248,0.20)' : u.role === 'secretary' ? 'rgba(167,139,250,0.20)' : 'rgba(34,197,94,0.20)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--f-display)', fontSize: 12, fontWeight: 600,
              color: u.role === 'admin' ? '#fff' : u.role === 'doctor' ? '#38BDF8' : u.role === 'secretary' ? '#A78BFA' : '#22C55E',
            }}>{u.email[0].toUpperCase()}</div>
            <div style={{ fontSize: 13, color: 'var(--t0)', fontFamily: 'var(--f-mono)' }}>{u.email}</div>
            <div>
              <span style={{
                fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                letterSpacing: '0.10em', textTransform: 'uppercase',
                padding: '3px 9px', borderRadius: 99,
                color: u.role === 'admin' ? '#fff' : u.role === 'doctor' ? '#38BDF8' : u.role === 'secretary' ? '#A78BFA' : '#22C55E',
                background: u.role === 'admin' ? 'rgba(139,92,246,0.20)' : u.role === 'doctor' ? 'rgba(56,189,248,0.10)' : u.role === 'secretary' ? 'rgba(167,139,250,0.10)' : 'rgba(34,197,94,0.10)',
                border: `1px solid ${u.role === 'admin' ? 'rgba(139,92,246,0.40)' : u.role === 'doctor' ? 'rgba(56,189,248,0.40)' : u.role === 'secretary' ? 'rgba(167,139,250,0.40)' : 'rgba(34,197,94,0.40)'}`,
              }}>{u.role}</span>
            </div>
            <div>
              <StatusPill tone={u.active ? 'sent' : 'skipped'} label={u.active ? 'Actif' : 'Désactivé'}/>
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: u.mfa ? '#22C55E' : 'var(--t4)' }}>
              {u.mfa ? '✓ activé' : '— off'}
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>{u.last}</div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button style={{
                width: 28, height: 28, borderRadius: 6, cursor: 'pointer',
                background: 'transparent', border: '1px solid var(--line)',
                color: 'var(--t3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>
              </button>
            </div>
          </div>
        ))}
      </div>

      {showCreate && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 100,
          background: 'rgba(0,0,0,0.60)', backdropFilter: 'blur(6px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowCreate(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{
            width: 420, background: 'var(--s1)', border: '1px solid var(--line-strong)',
            borderRadius: 16, padding: 24, boxShadow: '0 24px 80px rgba(0,0,0,0.6)',
          }}>
            <h3 style={{ fontFamily: 'var(--f-display)', fontSize: 18, fontWeight: 600, margin: '0 0 14px' }}>Créer un compte</h3>
            <div style={{ display: 'grid', gap: 12 }}>
              <input placeholder="email@medisense.ma" style={{
                padding: 10, background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
                color: 'var(--t0)', fontFamily: 'var(--f-body)', fontSize: 13, outline: 'none',
              }}/>
              <select style={{
                padding: 10, background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
                color: 'var(--t0)', fontSize: 13,
              }}>
                <option>doctor</option><option>secretary</option><option>admin</option>
              </select>
              <label style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--t1)' }}>
                <input type="checkbox" defaultChecked/> Forcer l'activation MFA
              </label>
              <label style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--t1)' }}>
                <input type="checkbox" defaultChecked/> Envoyer email d'invitation
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 18, justifyContent: 'flex-end' }}>
              <DashButton kind="ghost" onClick={() => setShowCreate(false)}>Annuler</DashButton>
              <DashButton kind="gradient" onClick={() => setShowCreate(false)}>Créer le compte</DashButton>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

// ───────────────── Rerank Eval ─────────────────
const RERANK_RRF = [
  { rank: 1, doc: 'Cardiologie · Insuffisance cardiaque ESC 2024', score: 0.94 },
  { rank: 2, doc: 'Protocole ECG · Douleur thoracique aiguë',       score: 0.91 },
  { rank: 3, doc: 'Chest pain triage · ESC guidelines',             score: 0.87 },
  { rank: 4, doc: 'BNP/NT-proBNP · interprétation clinique',        score: 0.82 },
  { rank: 5, doc: 'Furosémide · indications & posologie',           score: 0.78 },
];
const RERANK_CE = [
  { rank: 1, doc: 'Cardiologie · Insuffisance cardiaque ESC 2024', score: 0.94 },
  { rank: 2, doc: 'Protocole ECG · Douleur thoracique aiguë',       score: 0.91 },
  { rank: 3, doc: 'HF guidelines · ACC/AHA 2023',                   score: 0.87 },
  { rank: 4, doc: 'Chest pain triage · ESC guidelines',             score: 0.83 },
  { rank: 5, doc: 'BNP/NT-proBNP · interprétation clinique',        score: 0.79 },
];

function RankColumn({ title, sub, items, color }) {
  return (
    <div style={{
      flex: 1, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
      padding: 16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ width: 8, height: 8, borderRadius: 99, background: color, boxShadow: `0 0 6px ${color}` }}/>
        <div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600, color: 'var(--t0)' }}>{title}</div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>{sub}</div>
        </div>
      </div>
      <div style={{ display: 'grid', gap: 8 }}>
        {items.map(it => (
          <div key={it.rank} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
            background: 'var(--s2)', borderRadius: 8, border: '1px solid var(--line)',
          }}>
            <div style={{
              width: 22, height: 22, borderRadius: 99,
              background: 'var(--s3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600, color: 'var(--t1)',
            }}>{it.rank}</div>
            <div style={{ flex: 1, fontSize: 12, color: 'var(--t1)' }}>{it.doc}</div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color, fontWeight: 600 }}>{it.score.toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AdminRerank() {
  return (
    <DashboardLayout
      role="admin" active="rerank" onChange={() => {}}
      user={ADMIN_USER}
      breadcrumb="système · diagnostic rag"
      title="Évaluation Rerank — RRF vs Cross-Encoder"
      subtitle="Diagnostic qualité retrieval · sprint 3 · admin only"
    >
      {/* query input */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
        padding: 18, marginBottom: 18,
      }}>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
          Requête de test
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            defaultValue="douleurs thoraciques essoufflement insuffisance cardiaque"
            style={{
              flex: 1, padding: '11px 14px',
              background: 'var(--s2)', border: '1px solid var(--line-strong)', borderRadius: 10,
              color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12, outline: 'none',
            }}
          />
          <select style={{
            padding: '0 14px', background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 10,
            color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12,
          }}>
            <option>Top-5</option><option>Top-10</option><option>Top-20</option>
          </select>
          <DashButton kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M5 3l14 9-14 9z"/></svg>}>Lancer</DashButton>
        </div>
      </div>

      {/* metrics */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 18 }}>
        {[
          { label: 'Spearman ρ', value: '0.87', sub: 'corrélation des rangs',  c: '#22C55E' },
          { label: 'Top-3 overlap', value: '2/3', sub: 'documents communs',     c: '#A78BFA' },
          { label: 'MRR (RRF)',  value: '0.82', sub: 'mean reciprocal rank',   c: '#38BDF8' },
          { label: 'Latence CE', value: '142ms', sub: 'ms par requête',        c: '#F59E0B' },
        ].map(m => (
          <div key={m.label} style={{ flex: 1, padding: 16, background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{m.label}</div>
            <div style={{ fontFamily: 'var(--f-display)', fontSize: 28, fontWeight: 600, color: m.c, marginTop: 4, letterSpacing: '-0.02em' }}>{m.value}</div>
            <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 2 }}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* two columns */}
      <div style={{ display: 'flex', gap: 14 }}>
        <RankColumn title="RRF · Reciprocal Rank Fusion" sub="rapide · pas de modèle" items={RERANK_RRF} color="#A78BFA"/>
        <RankColumn title="Cross-Encoder · BAAI/bge-reranker" sub="précis · 142ms/req" items={RERANK_CE} color="#38BDF8"/>
      </div>

      <div style={{
        marginTop: 18, padding: '12px 16px',
        background: 'rgba(56,189,248,0.06)', border: '1px solid rgba(56,189,248,0.30)',
        borderRadius: 10, display: 'flex', alignItems: 'flex-start', gap: 12,
      }}>
        <div style={{ color: '#38BDF8', flexShrink: 0, marginTop: 2 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
        </div>
        <div style={{ fontSize: 12, color: 'var(--t1)', lineHeight: 1.55 }}>
          <strong style={{ color: 'var(--t0)' }}>Recommandation :</strong> sur cette requête, RRF maintient 2/3 des résultats du cross-encoder dans le top-3 pour une latence 14× inférieure. Garder RRF en production · CE uniquement pour l'admin tooling.
        </div>
      </div>
    </DashboardLayout>
  );
}

Object.assign(window, { AdminAudit, AdminUsers, AdminRerank });
