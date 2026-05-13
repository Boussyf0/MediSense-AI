'use client';
export type StatusTone =
  | 'pending' | 'sent' | 'failed' | 'skipped' | 'cb'
  | 'approved' | 'modified' | 'rejected' | 'info' | 'ai';

const TONE_CONFIG: Record<StatusTone, { c: string; bg: string; bd: string; label: string }> = {
  pending:  { c: '#F59E0B', bg: 'rgba(245,158,11,0.10)',  bd: 'rgba(245,158,11,0.40)',  label: 'En attente' },
  sent:     { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)',   label: 'Envoyé' },
  failed:   { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)',   label: 'Échec' },
  skipped:  { c: '#64748B', bg: 'rgba(100,116,139,0.10)', bd: 'rgba(100,116,139,0.30)', label: 'Ignoré' },
  cb:       { c: '#F43F5E', bg: 'rgba(244,63,94,0.12)',   bd: 'rgba(244,63,94,0.45)',   label: 'CB ouvert' },
  approved: { c: '#22C55E', bg: 'rgba(34,197,94,0.10)',   bd: 'rgba(34,197,94,0.40)',   label: 'Approuvé' },
  modified: { c: '#38BDF8', bg: 'rgba(56,189,248,0.10)',  bd: 'rgba(56,189,248,0.40)',  label: 'Modifié' },
  rejected: { c: '#EF4444', bg: 'rgba(239,68,68,0.10)',   bd: 'rgba(239,68,68,0.45)',   label: 'Rejeté' },
  info:     { c: '#94A3B8', bg: 'rgba(148,163,184,0.08)', bd: 'rgba(148,163,184,0.20)', label: 'Info' },
  ai:       { c: '#A78BFA', bg: 'rgba(167,139,250,0.10)', bd: 'rgba(167,139,250,0.40)', label: 'IA' },
};

interface Props { tone: StatusTone; label?: string; pulse?: boolean; }

export function StatusBadge({ tone, label, pulse = false }: Props) {
  const s = TONE_CONFIG[tone];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 9px', borderRadius: 99,
      background: s.bg, border: `1px solid ${s.bd}`,
      fontFamily: 'var(--f-mono)', fontSize: 10, color: s.c, fontWeight: 600,
      letterSpacing: '0.06em', textTransform: 'uppercase', whiteSpace: 'nowrap',
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: 99, background: s.c, flexShrink: 0,
        animation: pulse ? 'empty-pulse 1.5s ease-in-out infinite' : 'none',
        boxShadow: pulse ? `0 0 6px ${s.c}` : 'none',
      }} />
      {label ?? s.label}
    </span>
  );
}

export const StatusPill = StatusBadge;
