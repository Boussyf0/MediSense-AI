// Doctor screens: Login, Agenda, DPA 3-column

const { DashboardLayout, DashButton, RiskPill, StatusPill, ConfidenceBar } = window;

// Doctor-specific login (web-style centered card)
function DoctorLogin() {
  const [pw, setPw] = React.useState('••••••••••••');
  const [focusEmail, setFE] = React.useState(false);
  const [focusPw, setFP] = React.useState(false);
  return (
    <div style={{
      width: '100%', height: '100%', position: 'relative', overflow: 'hidden',
      background: 'var(--s0)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--f-body)',
    }}>
      {/* glow */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(700px 400px at 70% 30%, rgba(99,102,241,0.10), transparent 60%), radial-gradient(500px 400px at 20% 80%, rgba(139,92,246,0.07), transparent 60%)',
        pointerEvents: 'none',
      }}/>

      <div style={{ width: 420, position: 'relative', zIndex: 1 }}>
        {/* logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ display: 'inline-flex', alignItems: 'flex-end', gap: 3, height: 24, marginBottom: 12 }}>
            {[10, 18, 24, 18, 10].map((h, i) => (
              <div key={i} style={{
                width: 3.5, height: h, borderRadius: 2,
                background: 'var(--ai-grad)',
                animation: `wave-bar 1.4s ease-in-out ${i * 0.15}s infinite`,
                transformOrigin: 'bottom',
              }}/>
            ))}
          </div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 22, fontWeight: 600, letterSpacing: '-0.01em' }}>
            MediSense<span className="grad-text"> AI</span>
          </div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 4 }}>
            Console clinique
          </div>
        </div>

        {/* card */}
        <div style={{
          background: 'var(--s1)',
          border: '1px solid var(--line)',
          borderRadius: 16, padding: 28,
          boxShadow: '0 12px 48px rgba(0,0,0,0.4)',
        }}>
          <h2 style={{ fontFamily: 'var(--f-display)', fontSize: 24, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.01em' }}>Connexion</h2>
          <div style={{ color: 'var(--t2)', fontSize: 13, marginBottom: 22 }}>Accès médecin · authentification SSO</div>

          {/* email */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>Email professionnel</div>
            <div style={{ position: 'relative' }}>
              <input
                type="email"
                defaultValue="dr.merrouni@clinique.ma"
                onFocus={() => setFE(true)} onBlur={() => setFE(false)}
                style={{
                  width: '100%', padding: '11px 13px',
                  background: 'var(--s2)',
                  border: 'none', borderBottom: '1px solid var(--line-strong)',
                  borderRadius: '8px 8px 0 0', color: 'var(--t0)',
                  fontFamily: 'var(--f-body)', fontSize: 13.5, outline: 'none',
                }}
              />
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                height: 2, borderRadius: 99,
                background: 'var(--ai-grad)',
                transform: focusEmail ? 'scaleX(1)' : 'scaleX(0)',
                transformOrigin: 'left', transition: 'transform .25s ease',
                boxShadow: focusEmail ? '0 0 12px rgba(139,92,246,0.5)' : 'none',
              }}/>
            </div>
          </div>

          {/* password */}
          <div style={{ marginBottom: 22 }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>Mot de passe</div>
            <div style={{ position: 'relative' }}>
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                onFocus={() => setFP(true)} onBlur={() => setFP(false)}
                style={{
                  width: '100%', padding: '11px 40px 11px 13px',
                  background: 'var(--s2)',
                  border: 'none', borderBottom: '1px solid var(--line-strong)',
                  borderRadius: '8px 8px 0 0', color: 'var(--t0)',
                  fontFamily: 'var(--f-body)', fontSize: 13.5, outline: 'none',
                }}
              />
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                height: 2, borderRadius: 99,
                background: 'var(--ai-grad)',
                transform: focusPw ? 'scaleX(1)' : 'scaleX(0)',
                transformOrigin: 'left', transition: 'transform .25s ease',
                boxShadow: focusPw ? '0 0 12px rgba(139,92,246,0.5)' : 'none',
              }}/>
              <button style={{
                position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                background: 'transparent', border: 'none', color: 'var(--t3)', cursor: 'pointer',
                width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
            <div style={{ marginTop: 8, fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>
              <a href="#" style={{ color: '#A78BFA', textDecoration: 'none' }}>Mot de passe oublié ?</a>
            </div>
          </div>

          <button style={{
            width: '100%', padding: '12px', borderRadius: 99,
            background: 'var(--ai-grad)', color: '#fff', border: 'none',
            fontFamily: 'var(--f-body)', fontSize: 14, fontWeight: 600,
            cursor: 'pointer', boxShadow: '0 8px 24px rgba(99,102,241,0.30)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
            Se connecter
            <span>→</span>
          </button>
        </div>

        <div style={{
          textAlign: 'center', marginTop: 18,
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t4)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>
          v1.0 · n.synergy · EMSI Marrakech
        </div>
      </div>
    </div>
  );
}

// ───────────────── Doctor Agenda ─────────────────
const DOCTOR_USER = { initial: 'M', name: 'Dr. Merrouni' };

const APPTS = [
  { time: '09:00', uid: 'a1b2c3d4', name: 'Ahmed Benali',     type: 'Consultation cardiologie', risk: 'danger', prob: 0.67, status: 'pending', sms: 0 },
  { time: '09:30', uid: 'e5f6g7h8', name: 'Salma Idrissi',    type: 'Suivi diabète',            risk: 'safe',   prob: 0.08, status: 'confirmed', sms: 1 },
  { time: '10:00', uid: 'i9j0k1l2', name: 'Karim Ouahbi',     type: 'Bilan annuel',             risk: 'warn',   prob: 0.34, status: 'confirmed', sms: 1 },
  { time: '10:30', uid: 'm3n4o5p6', name: 'Fatima El Amrani', type: 'Renouvellement traitement',risk: 'safe',   prob: 0.12, status: 'pending',  sms: 0 },
  { time: '11:00', uid: 'q7r8s9t0', name: 'Youssef Tazi',     type: 'Téléconsultation',         risk: 'danger', prob: 0.71, status: 'pending',  sms: 0 },
  { time: '11:30', uid: 'u1v2w3x4', name: 'Nadia Berrada',    type: 'Consultation générale',    risk: 'safe',   prob: 0.14, status: 'confirmed', sms: 1 },
  { time: '14:00', uid: 'y5z6a7b8', name: 'Hamza Saidi',      type: 'Échographie cardiaque',    risk: 'warn',   prob: 0.28, status: 'confirmed', sms: 1 },
];

function StatCard({ count, color, glow, label, sublabel }) {
  return (
    <div style={{
      flex: 1,
      background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
      padding: '18px 20px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{
          width: 8, height: 8, borderRadius: 99, background: color,
          boxShadow: `0 0 8px ${glow}`,
        }}/>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{label}</span>
      </div>
      <div style={{ fontFamily: 'var(--f-display)', fontSize: 36, fontWeight: 600, color: 'var(--t0)', lineHeight: 1, letterSpacing: '-0.02em' }}>
        {count}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--t2)', marginTop: 6 }}>{sublabel}</div>
    </div>
  );
}

function DoctorAgenda({ onOpenDpa }) {
  const counts = APPTS.reduce((acc, a) => { acc[a.risk]++; return acc; }, { safe: 0, warn: 0, danger: 0 });
  const totalSms = APPTS.filter(a => a.sms).length;

  return (
    <DashboardLayout
      role="doctor" active="agenda" onChange={() => {}}
      user={DOCTOR_USER}
      breadcrumb="agenda · 10 mai 2026"
      title="Agenda intelligent"
      subtitle="Prédiction no-show · XGBoost v2.1 · 7 rendez-vous aujourd'hui"
      actions={[
        <DashButton key="d" kind="solid" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>}>10 mai 2026</DashButton>,
        <DashButton key="r" kind="solid" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5"/></svg>}>Actualiser</DashButton>,
        <DashButton key="s" kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8l9 6 9-6M3 8v10a2 2 0 002 2h14a2 2 0 002-2V8M3 8l2-3h14l2 3"/></svg>}>SMS de rappel ({counts.danger + counts.warn})</DashButton>,
      ]}
    >
      {/* stat row */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 20 }}>
        <StatCard count={counts.safe}   color="#22C55E" glow="rgba(34,197,94,0.55)"   label="Faible"  sublabel="probabilité < 20% — pas d'action"/>
        <StatCard count={counts.warn}   color="#F97316" glow="rgba(249,115,22,0.55)"  label="Modéré"  sublabel="20–40% — SMS recommandé"/>
        <StatCard count={counts.danger} color="#EF4444" glow="rgba(239,68,68,0.55)"   label="Élevé"   sublabel="> 40% — appel + SMS"/>
        <StatCard count={totalSms}      color="#A78BFA" glow="rgba(167,139,250,0.55)" label="SMS env" sublabel="rappels déjà dispatchés"/>
      </div>

      {/* table */}
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
        overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: '90px 1fr 200px 140px 130px 100px 80px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 500,
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Heure</div>
          <div>Patient</div>
          <div>Motif</div>
          <div>No-show</div>
          <div>Statut</div>
          <div>SMS</div>
          <div></div>
        </div>
        {APPTS.map((a, i) => (
          <button key={a.uid} onClick={onOpenDpa}
            style={{
              all: 'unset',
              cursor: 'pointer',
              display: 'grid', gridTemplateColumns: '90px 1fr 200px 140px 130px 100px 80px',
              padding: '13px 18px', alignItems: 'center',
              borderBottom: i < APPTS.length - 1 ? '1px solid var(--line)' : 'none',
              transition: 'background .14s',
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(99,102,241,0.06)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 500, color: 'var(--t0)' }}>{a.time}</div>
            <div>
              <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{a.name}</div>
              <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>uid · {a.uid}</div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--t2)' }}>{a.type}</div>
            <div><RiskPill level={a.risk} prob={a.prob}/></div>
            <div>
              <StatusPill tone={a.status === 'pending' ? 'pending' : 'approved'} label={a.status === 'pending' ? 'En attente' : 'Confirmé'} pulse={a.status === 'pending'}/>
            </div>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: a.sms ? '#22C55E' : 'var(--t4)' }}>
              {a.sms ? '✓ envoyé' : '— '}
            </div>
            <div style={{ textAlign: 'right', color: 'var(--t3)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 6l6 6-6 6"/></svg>
            </div>
          </button>
        ))}
      </div>

      <div style={{
        marginTop: 22, padding: '14px 18px',
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: 8,
          background: 'rgba(167,139,250,0.10)',
          border: '1px solid rgba(167,139,250,0.30)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#A78BFA',
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4l3 2"/></svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12.5, color: 'var(--t0)', fontWeight: 500 }}>Modèle XGBoost re-entraîné <span style={{ fontFamily: 'var(--f-mono)', color: 'var(--t3)' }}>il y a 4h</span></div>
          <div style={{ fontSize: 11.5, color: 'var(--t2)' }}>AUC 0.847 · F1 0.79 · entrainé sur 14 728 RDVs (90 derniers jours).</div>
        </div>
        <DashButton kind="solid" small>Voir métriques</DashButton>
      </div>
    </DashboardLayout>
  );
}

// ───────────────── DPA 3-column ─────────────────
function DpaCol({ tag, title, count, children }) {
  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      <div style={{
        padding: '14px 18px', borderBottom: '1px solid var(--line)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.16em', textTransform: 'uppercase' }}>{tag}</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 15, fontWeight: 600, color: 'var(--t0)', marginTop: 2 }}>{title}</div>
        </div>
        {count !== undefined && (
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
            padding: '2px 8px', background: 'var(--s2)', borderRadius: 99,
            border: '1px solid var(--line)',
          }}>{count}</div>
        )}
      </div>
      <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }} className="scroll-hide">
        {children}
      </div>
    </div>
  );
}

function SymptomItem({ text, severity, since }) {
  const sevColors = { high: '#EF4444', med: '#F97316', low: '#22C55E' };
  return (
    <div style={{
      display: 'flex', gap: 10, padding: '11px 12px',
      background: 'var(--s2)', borderRadius: 10, border: '1px solid var(--line)',
    }}>
      <div style={{
        width: 6, alignSelf: 'stretch', borderRadius: 99,
        background: sevColors[severity], boxShadow: `0 0 6px ${sevColors[severity]}80`, flexShrink: 0,
      }}/>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12.5, color: 'var(--t0)', fontWeight: 500 }}>{text}</div>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>{since}</div>
      </div>
    </div>
  );
}

function VitalItem({ label, value, unit, status, threshold, ago, tone }) {
  const tones = {
    critical: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)', bd: 'rgba(239,68,68,0.45)' },
    warn:     { c: '#F97316', bg: 'rgba(249,115,22,0.10)', bd: 'rgba(249,115,22,0.45)' },
    normal:   { c: '#22C55E', bg: 'rgba(34,197,94,0.08)',  bd: 'rgba(34,197,94,0.30)' },
  };
  const t = tones[tone];
  return (
    <div style={{
      padding: '12px 14px', background: 'var(--s2)', borderRadius: 10,
      border: `1px solid ${t.bd}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <div style={{ fontSize: 12, color: 'var(--t2)' }}>{label}</div>
        <StatusPill tone={tone === 'critical' ? 'failed' : tone === 'warn' ? 'pending' : 'sent'} label={status}/>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'var(--f-display)', fontSize: 26, fontWeight: 600, color: t.c, letterSpacing: '-0.02em' }}>{value}</span>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)' }}>{unit}</span>
      </div>
      <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 4 }}>{threshold} · {ago}</div>
    </div>
  );
}

function ActionCard({ kind, title, description, rationale, confidence, state, onApprove, onReject, onEdit }) {
  // kind: prescribe | refer | monitor | alert
  const kinds = {
    prescribe: { c: '#38BDF8', label: 'PRESCRIRE', icon: '℞' },
    refer:     { c: '#A78BFA', label: 'RÉFÉRER',   icon: '↗' },
    monitor:   { c: '#FBBF24', label: 'MONITORER', icon: '◔' },
    alert:     { c: '#EF4444', label: 'ALERTER',   icon: '⚠' },
  };
  const k = kinds[kind];
  const isApproved = state === 'approved';
  const isRejected = state === 'rejected';
  const opacity = isRejected ? 0.5 : 1;
  return (
    <div style={{
      background: isApproved ? 'rgba(34,197,94,0.06)' : isRejected ? 'rgba(239,68,68,0.05)' : 'var(--s2)',
      border: `1px solid ${isApproved ? 'rgba(34,197,94,0.30)' : isRejected ? 'rgba(239,68,68,0.30)' : 'var(--line)'}`,
      borderRadius: 12, padding: 14, opacity,
      transition: 'all .25s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '3px 9px', borderRadius: 99,
          fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
          color: k.c, background: `${k.c}1A`, border: `1px solid ${k.c}66`,
          letterSpacing: '0.08em',
        }}>
          <span>{k.icon}</span>{k.label}
        </span>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t1)', fontWeight: 600 }}>
          {Math.round(confidence * 100)}%
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ flex: 1, height: 4, background: 'var(--s3)', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{ width: `${confidence * 100}%`, height: '100%', background: 'var(--ai-grad)' }}/>
        </div>
      </div>
      <div style={{ fontSize: 13.5, color: 'var(--t0)', fontWeight: 600, marginBottom: 4, lineHeight: 1.3, textDecoration: isRejected ? 'line-through' : 'none' }}>
        {title}
      </div>
      <div style={{ fontSize: 12, color: 'var(--t1)', marginBottom: 8, lineHeight: 1.5 }}>{description}</div>
      <div style={{ fontSize: 11.5, color: 'var(--t3)', fontStyle: 'italic', lineHeight: 1.5, marginBottom: 12, paddingLeft: 10, borderLeft: '2px solid var(--s3)' }}>
        {rationale}
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={onApprove} style={{
          flex: 1, padding: '7px 8px', borderRadius: 8, cursor: 'pointer',
          background: isApproved ? 'rgba(34,197,94,0.20)' : 'rgba(34,197,94,0.08)',
          border: `1px solid ${isApproved ? 'rgba(34,197,94,0.6)' : 'rgba(34,197,94,0.30)'}`,
          color: '#22C55E', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M5 12l5 5L20 7"/></svg>
          {isApproved ? 'Approuvé' : 'Approuver'}
        </button>
        <button onClick={onReject} style={{
          flex: 1, padding: '7px 8px', borderRadius: 8, cursor: 'pointer',
          background: isRejected ? 'rgba(239,68,68,0.18)' : 'rgba(239,68,68,0.06)',
          border: `1px solid ${isRejected ? 'rgba(239,68,68,0.6)' : 'rgba(239,68,68,0.25)'}`,
          color: '#EF4444', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M6 6l12 12M18 6L6 18"/></svg>
          Rejeter
        </button>
        <button onClick={onEdit} style={{
          padding: '7px 10px', borderRadius: 8, cursor: 'pointer',
          background: 'var(--s3)', border: '1px solid var(--line-strong)',
          color: 'var(--t1)', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 500,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4z"/></svg>
        </button>
      </div>
    </div>
  );
}

function DoctorDpa({ onBack }) {
  const [actions, setActions] = React.useState({
    a1: 'approved', a2: 'pending', a3: 'pending', a4: 'pending',
  });
  const [note, setNote] = React.useState('');

  const setA = (k, v) => setActions(prev => ({ ...prev, [k]: v }));

  return (
    <DashboardLayout
      role="doctor" active="agenda" onChange={() => {}}
      user={DOCTOR_USER}
      breadcrumb="agenda › ahmed benali · 09:00"
      title="Résumé DPA — Ahmed Benali"
      subtitle="Patient ID a1b2c3d4 · cardiologie · généré il y a 3 min par le pipeline RAG"
      actions={[
        <DashButton key="b" kind="ghost" onClick={onBack} icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>}>Retour à l'agenda</DashButton>,
        <DashButton key="r" kind="solid" small>Rejeter le résumé</DashButton>,
        <DashButton key="v" kind="gradient" icon={<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12l5 5L20 7"/></svg>}>Valider et signer</DashButton>,
      ]}
    >
      {/* status banner */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 18,
        padding: '14px 18px',
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
        marginBottom: 16,
      }}>
        <StatusPill tone="pending" label="En attente · 1 action approuvée" pulse/>
        <ConfidenceBar value={0.78} label="Confiance globale" width={200}/>
        <div style={{ flex: 1 }}/>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)' }}>
          rag · 3 sources · maj il y a 3 min
        </div>
      </div>

      {/* 3 columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.2fr', gap: 14, height: 'calc(100% - 80px)', minHeight: 480 }}>
        <DpaCol tag="rag · sprint 3" title="Symptômes rapportés" count="4">
          <SymptomItem text="Douleurs thoraciques à l'effort" severity="high" since="depuis 5 jours · échelle 7/10"/>
          <SymptomItem text="Essoufflement nocturne" severity="med" since="depuis 2 semaines · épisodique"/>
          <SymptomItem text="Toux persistante (sèche)" severity="med" since="depuis 3 jours"/>
          <SymptomItem text="Fatigue inhabituelle" severity="low" since="depuis 1 semaine"/>
          <div style={{
            padding: '10px 12px', background: 'rgba(99,102,241,0.06)',
            borderRadius: 10, border: '1px solid rgba(99,102,241,0.30)',
            marginTop: 4,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'var(--f-mono)', fontSize: 9.5, color: '#A78BFA', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>
              <span>≋</span>Synthèse RAG
            </div>
            <div style={{ fontSize: 11.5, color: 'var(--t1)', lineHeight: 1.5 }}>
              Tableau évocateur d'une <strong style={{ color: 'var(--t0)' }}>insuffisance cardiaque débutante</strong>. À corréler avec la biométrie et l'ECG.
            </div>
          </div>
        </DpaCol>

        <DpaCol tag="iot · sprint 7" title="Biométrie 24h" count="3 anomalies">
          <VitalItem label="Saturation O₂" value="91" unit="% SpO2" status="critique" threshold="< 95% — anormal" ago="il y a 2 h" tone="critical"/>
          <VitalItem label="Variabilité HRV" value="28" unit="ms" status="modéré" threshold="< 35 ms — bas" ago="moy. 24h" tone="warn"/>
          <VitalItem label="Fréquence cardiaque" value="72" unit="bpm" status="normal" threshold="60–100 bpm" ago="repos · stable" tone="normal"/>
          <div style={{
            padding: '10px 12px', background: 'var(--s2)', borderRadius: 10,
            border: '1px solid var(--line)',
          }}>
            <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>Tendance 7 jours</div>
            {/* sparkline */}
            <svg width="100%" height="40" viewBox="0 0 200 40" preserveAspectRatio="none">
              <defs>
                <linearGradient id="dpa-spark" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0" stopColor="#EF4444" stopOpacity="0.5"/>
                  <stop offset="1" stopColor="#EF4444" stopOpacity="0"/>
                </linearGradient>
              </defs>
              <path d="M 0 8 L 25 12 L 50 18 L 75 14 L 100 22 L 125 28 L 150 32 L 175 35 L 200 38" fill="none" stroke="#EF4444" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M 0 8 L 25 12 L 50 18 L 75 14 L 100 22 L 125 28 L 150 32 L 175 35 L 200 38 L 200 40 L 0 40 Z" fill="url(#dpa-spark)"/>
            </svg>
            <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 4 }}>SpO₂ ↓ progressif sur 7 jours · −5 pts</div>
          </div>
        </DpaCol>

        <DpaCol tag="xgboost · sprint 5" title="Actions IA suggérées" count="4 actions">
          <ActionCard kind="prescribe"
            title="Prescrire Furosémide 40 mg"
            description="1 cp par jour le matin pendant 14 jours, surveillance kaliémie à J7"
            rationale="Tableau d'IC débutante avec congestion (SpO2 ↓, essoufflement) · adapté au profil rénal du patient"
            confidence={0.85}
            state={actions.a1}
            onApprove={() => setA('a1', actions.a1 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a1', 'rejected')}
            onEdit={() => {}}
          />
          <ActionCard kind="refer"
            title="Référer en cardiologie"
            description="ETT (échographie cardiaque) sous 72h pour évaluer la fraction d'éjection"
            rationale="Signes cliniques + biométrie suggèrent une atteinte structurelle à confirmer par imagerie"
            confidence={0.62}
            state={actions.a2}
            onApprove={() => setA('a2', actions.a2 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a2', 'rejected')}
            onEdit={() => {}}
          />
          <ActionCard kind="monitor"
            title="Monitoring SpO₂ rapproché"
            description="Bracelet IoT actif · alerte palier si SpO₂ < 90% · seuil HRV à 25 ms"
            rationale="Tendance baissière sur 7 jours nécessite surveillance avant réévaluation"
            confidence={0.91}
            state={actions.a3}
            onApprove={() => setA('a3', actions.a3 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a3', 'rejected')}
            onEdit={() => {}}
          />
          <ActionCard kind="alert"
            title="Alerter en cas d'aggravation"
            description="Notification SAMU 141 si SpO2 < 88% pendant > 5 min ou nouvelle douleur"
            rationale="Sécurisation du suivi entre les consultations · seuils conformes recommandations ESC 2024"
            confidence={0.74}
            state={actions.a4}
            onApprove={() => setA('a4', actions.a4 === 'approved' ? 'pending' : 'approved')}
            onReject={() => setA('a4', 'rejected')}
            onEdit={() => {}}
          />
        </DpaCol>
      </div>

      {/* note */}
      <div style={{
        marginTop: 16,
        background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
        padding: 14,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4z"/></svg>
          <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Note du médecin (optionnel · audité)</span>
        </div>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Observations cliniques, contexte du patient, justification d'une modification…"
          style={{
            width: '100%', minHeight: 60, resize: 'vertical',
            background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
            color: 'var(--t0)', padding: 10,
            fontFamily: 'var(--f-body)', fontSize: 13, outline: 'none',
          }}
        />
      </div>
    </DashboardLayout>
  );
}

Object.assign(window, { DoctorLogin, DoctorAgenda, DoctorDpa });
