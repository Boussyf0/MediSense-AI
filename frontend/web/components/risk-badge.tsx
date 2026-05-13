'use client';
type RiskLevel = 'safe' | 'warn' | 'danger' | null;

const RISK_CONFIG: Record<Exclude<RiskLevel, null>, { c: string; bg: string; bd: string; glyph: string }> = {
  safe:   { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',  bd: 'rgba(34,197,94,0.40)',  glyph: '✓' },
  warn:   { c: '#F97316', bg: 'rgba(249,115,22,0.10)', bd: 'rgba(249,115,22,0.40)', glyph: '⚠' },
  danger: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',  bd: 'rgba(239,68,68,0.45)',  glyph: '●' },
};

interface Props { level: RiskLevel; prob?: number; }

export function RiskBadge({ level, prob }: Props) {
  if (!level) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        padding: '3px 9px', borderRadius: 99,
        background: 'var(--s2)', border: '1px solid var(--line)',
        fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
        whiteSpace: 'nowrap',
      }}>○ —</span>
    );
  }
  const s = RISK_CONFIG[level];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 99,
      background: s.bg, border: `1px solid ${s.bd}`,
      fontFamily: 'var(--f-mono)', fontSize: 10.5, color: s.c, fontWeight: 600,
      whiteSpace: 'nowrap',
    }}>
      {s.glyph} {prob !== undefined ? `${Math.round(prob * 100)}%` : ''}
    </span>
  );
}

export const RiskPill = RiskBadge;
