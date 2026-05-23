// Dashboard shell — sidebar + main content area for Next.js-style web dashboards
// Used by Doctor / Secretary / Admin

const { IconChat: _IC1 } = window;

function DashSidebar({ role, active, onChange, user }) {
  // role: 'doctor' | 'secretary' | 'admin'
  const items = role === 'doctor' ? [
    { key: 'agenda', label: 'Agenda', icon: 'cal' },
    { key: 'patients', label: 'Patients', icon: 'users' },
    { key: 'dpa', label: 'Résumés DPA', icon: 'doc' },
  ] : role === 'secretary' ? [
    { key: 'agenda', label: 'Agenda', icon: 'cal' },
    { key: 'crm', label: 'Tâches CRM', icon: 'sync' },
    { key: 'feedback', label: 'Feedback ML', icon: 'check' },
  ] : [
    { key: 'audit', label: 'Logs RGPD', icon: 'shield' },
    { key: 'users', label: 'Utilisateurs', icon: 'users' },
    { key: 'rerank', label: 'Rerank Eval', icon: 'flask' },
    { key: 'system', label: 'Système', icon: 'cpu' },
  ];

  const Icon = ({ k, color }) => {
    const s = { width: 18, height: 18, stroke: color, strokeWidth: 1.7, fill: 'none', strokeLinecap: 'round', strokeLinejoin: 'round' };
    if (k === 'cal') return <svg viewBox="0 0 24 24" {...s}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>;
    if (k === 'users') return <svg viewBox="0 0 24 24" {...s}><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 6a3 3 0 010 6M21 20c0-2.5-1.5-4.5-4-5.5"/></svg>;
    if (k === 'doc') return <svg viewBox="0 0 24 24" {...s}><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z"/><path d="M14 3v6h6M9 13h6M9 17h4"/></svg>;
    if (k === 'sync') return <svg viewBox="0 0 24 24" {...s}><path d="M3 12a9 9 0 0115-6.7L21 8M21 3v5h-5M21 12a9 9 0 01-15 6.7L3 16M3 21v-5h5"/></svg>;
    if (k === 'check') return <svg viewBox="0 0 24 24" {...s}><path d="M5 12l5 5L20 7"/></svg>;
    if (k === 'shield') return <svg viewBox="0 0 24 24" {...s}><path d="M12 3l8 3v6c0 5-3.5 8.5-8 9-4.5-.5-8-4-8-9V6l8-3z"/><path d="M9 12l2 2 4-4"/></svg>;
    if (k === 'flask') return <svg viewBox="0 0 24 24" {...s}><path d="M9 3h6M10 3v6L5 19a2 2 0 002 2h10a2 2 0 002-2L14 9V3"/><path d="M7 15h10"/></svg>;
    if (k === 'cpu') return <svg viewBox="0 0 24 24" {...s}><rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M3 9h3M3 15h3M18 9h3M18 15h3M9 3v3M15 3v3M9 18v3M15 18v3"/></svg>;
    return null;
  };

  return (
    <div style={{
      width: 220, flexShrink: 0,
      background: 'var(--s1)',
      borderRight: '1px solid var(--line)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* logo */}
      <div style={{ padding: '20px 18px 18px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 18 }}>
            {[8, 14, 18, 14, 8].map((h, i) => (
              <div key={i} style={{
                width: 2.5, height: h, borderRadius: 2,
                background: 'var(--ai-grad)',
                opacity: 0.7 + (i === 2 ? 0.3 : 0),
              }}/>
            ))}
          </div>
          <div style={{ fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 14, color: 'var(--t0)', letterSpacing: '-0.01em' }}>
            MediSense<span className="grad-text"> AI</span>
          </div>
        </div>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)', letterSpacing: '0.16em', textTransform: 'uppercase', marginTop: 4 }}>
          {role === 'doctor' ? 'console clinique' : role === 'secretary' ? 'console secrétariat' : 'console admin'}
        </div>
      </div>

      {/* nav */}
      <div style={{ flex: 1, padding: '14px 10px', overflowY: 'auto' }} className="scroll-hide">
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)', letterSpacing: '0.16em', textTransform: 'uppercase', padding: '6px 8px 8px' }}>
          Navigation
        </div>
        {items.map(it => {
          const isActive = active === it.key;
          return (
            <button key={it.key} onClick={() => onChange(it.key)} style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 10,
              padding: '9px 10px', marginBottom: 2,
              background: isActive ? 'var(--s2)' : 'transparent',
              border: 'none', borderLeft: `2px solid ${isActive ? '#8B5CF6' : 'transparent'}`,
              color: isActive ? 'var(--t0)' : 'var(--t2)',
              fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: isActive ? 500 : 400,
              cursor: 'pointer', textAlign: 'left', borderRadius: 6,
              transition: 'all .15s',
            }}>
              <Icon k={it.icon} color={isActive ? '#A78BFA' : '#64748B'}/>
              <span>{it.label}</span>
            </button>
          );
        })}
      </div>

      {/* user */}
      <div style={{ borderTop: '1px solid var(--line)', padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 99,
          background: 'var(--ai-grad)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--f-display)', fontSize: 13, fontWeight: 600, color: '#fff',
        }}>{user.initial}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: 'var(--f-body)', fontSize: 12, fontWeight: 500, color: 'var(--t0)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.name}</div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>{role}</div>
        </div>
        <button title="Logout" style={{
          background: 'transparent', border: '1px solid var(--line)', color: 'var(--t3)',
          width: 26, height: 26, borderRadius: 6, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/></svg>
        </button>
      </div>
    </div>
  );
}

function DashTopBar({ title, subtitle, breadcrumb, actions }) {
  return (
    <div style={{
      padding: '20px 28px 18px',
      borderBottom: '1px solid var(--line)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16,
      background: 'rgba(15, 22, 35, 0.3)',
    }}>
      <div style={{ minWidth: 0 }}>
        {breadcrumb && (
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
            {breadcrumb}
          </div>
        )}
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
          color: 'var(--t0)', margin: 0, letterSpacing: '-0.01em',
        }}>{title}</h1>
        {subtitle && (
          <div style={{ color: 'var(--t2)', fontSize: 12.5, marginTop: 4 }}>{subtitle}</div>
        )}
      </div>
      {actions && <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>{actions}</div>}
    </div>
  );
}

// Generic dashboard layout
function DashboardLayout({ role, active, onChange, user, title, subtitle, breadcrumb, actions, children }) {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'var(--s0)',
      display: 'flex', overflow: 'hidden',
      fontFamily: 'var(--f-body)',
    }}>
      <DashSidebar role={role} active={active} onChange={onChange} user={user}/>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <DashTopBar title={title} subtitle={subtitle} breadcrumb={breadcrumb} actions={actions}/>
        <div style={{ flex: 1, overflowY: 'auto', padding: '22px 28px' }} className="scroll-hide">
          {children}
        </div>
      </div>
    </div>
  );
}

// Risk pill
function RiskPill({ level, prob }) {
  // level: 'safe' | 'warn' | 'danger' | null
  const colors = {
    safe:   { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',  bd: 'rgba(34,197,94,0.40)',  glyph: '✓' },
    warn:   { c: '#F97316', bg: 'rgba(249,115,22,0.10)', bd: 'rgba(249,115,22,0.40)', glyph: '⚠' },
    danger: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',  bd: 'rgba(239,68,68,0.45)',  glyph: '●' },
  };
  if (!level) {
    return <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px',
      borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
      background: 'var(--s2)', border: '1px solid var(--line)', whiteSpace: 'nowrap',
    }}>○ —</span>;
  }
  const s = colors[level];
  return <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px',
    borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 10.5, fontWeight: 600,
    color: s.c, background: s.bg, border: `1px solid ${s.bd}`, whiteSpace: 'nowrap',
  }}>{s.glyph} {Math.round(prob * 100)}%</span>;
}

// Status dot pill (CRM, audit, etc)
function StatusPill({ tone, label, pulse }) {
  const tones = {
    pending:  { c: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  bd: 'rgba(245,158,11,0.40)' },
    sent:     { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)' },
    failed:   { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)' },
    skipped:  { c: '#64748B', bg: 'rgba(100,116,139,0.10)', bd: 'rgba(100,116,139,0.30)' },
    cb:       { c: '#F43F5E', bg: 'rgba(244,63,94,0.12)',   bd: 'rgba(244,63,94,0.45)' },
    approved: { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)' },
    modified: { c: '#38BDF8', bg: 'rgba(56,189,248,0.10)',  bd: 'rgba(56,189,248,0.40)' },
    rejected: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)' },
    info:     { c: '#94A3B8', bg: 'rgba(148,163,184,0.08)', bd: 'rgba(148,163,184,0.20)' },
    ai:       { c: '#A78BFA', bg: 'rgba(167,139,250,0.10)', bd: 'rgba(167,139,250,0.40)' },
  };
  const s = tones[tone] || tones.info;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 9px',
      borderRadius: 99, fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
      color: s.c, background: s.bg, border: `1px solid ${s.bd}`,
      letterSpacing: '0.06em', textTransform: 'uppercase', whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: 99, background: s.c,
        animation: pulse ? 'empty-pulse 1.5s ease-in-out infinite' : 'none',
        boxShadow: pulse ? `0 0 6px ${s.c}` : 'none',
      }}/>
      {label}
    </span>
  );
}

// Confidence bar
function ConfidenceBar({ value, label = 'Confiance', width = 160 }) {
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</span>
      <div style={{ width, height: 5, background: 'var(--s3)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{
          width: `${value * 100}%`, height: '100%',
          background: 'var(--ai-grad)',
          borderRadius: 99, transition: 'width .8s ease-out',
        }}/>
      </div>
      <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t0)', fontWeight: 600 }}>{Math.round(value * 100)}%</span>
    </div>
  );
}

// Compact button
function DashButton({ kind = 'ghost', icon, children, onClick, danger, small }) {
  const padY = small ? 6 : 8;
  const padX = small ? 11 : 14;
  const fs = small ? 11.5 : 12.5;

  let style;
  if (kind === 'gradient') {
    style = {
      background: 'var(--ai-grad)',
      color: '#fff',
      border: 'none',
      boxShadow: '0 4px 16px rgba(99,102,241,0.30)',
    };
  } else if (kind === 'solid') {
    style = {
      background: danger ? 'rgba(239,68,68,0.12)' : 'var(--s2)',
      color: danger ? '#FCA5A5' : 'var(--t0)',
      border: `1px solid ${danger ? 'rgba(239,68,68,0.40)' : 'var(--line-strong)'}`,
    };
  } else {
    style = {
      background: 'transparent',
      color: 'var(--t1)',
      border: '1px solid var(--line)',
    };
  }
  return (
    <button onClick={onClick} style={{
      ...style,
      padding: `${padY}px ${padX}px`, borderRadius: 8,
      fontFamily: 'var(--f-body)', fontSize: fs, fontWeight: 500,
      cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 7,
      whiteSpace: 'nowrap', transition: 'transform .12s, box-shadow .12s',
    }}>
      {icon}
      {children}
    </button>
  );
}

Object.assign(window, { DashSidebar, DashTopBar, DashboardLayout, RiskPill, StatusPill, ConfidenceBar, DashButton });
