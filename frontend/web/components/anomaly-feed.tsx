'use client';
import { useEffect, useRef, useState, useCallback } from 'react';
import { useAlerts } from './AlertsProvider';

// ─── helpers ─────────────────────────────────────────────────────────────────

function relativeTime(ts: number): string {
  const diffS = Math.floor((Date.now() - ts) / 1000);
  if (diffS < 60) return 'à l\'instant';
  if (diffS < 3600) return `il y a ${Math.floor(diffS / 60)} min`;
  if (diffS < 86400) return `il y a ${Math.floor(diffS / 3600)} h`;
  return `il y a ${Math.floor(diffS / 86400)} j`;
}

function maskPhone(phone: string): string {
  if (phone.length < 6) return phone;
  return phone.slice(0, 4) + ' ••• ' + phone.slice(-3);
}

interface VitalChipProps {
  label: string;
  value: string | number;
  color: string;
}
function VitalChip({ label, value, color }: VitalChipProps) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 99,
      background: `${color}18`,
      border: `1px solid ${color}40`,
      fontSize: 10.5, fontFamily: 'var(--f-mono)',
      color, fontWeight: 600, letterSpacing: '0.04em',
      whiteSpace: 'nowrap',
    }}>
      {label} {value}
    </span>
  );
}

// ─── call patient modal ─────────────────────────────────────────────────────

type CallStatus = 'idle' | 'ringing' | 'connected' | 'ended' | 'failed';

interface CallPatientModalProps {
  patientUuid: string;
  narrative: string;
  onClose: () => void;
}

function CallPatientModal({ patientUuid, narrative, onClose }: CallPatientModalProps) {
  const [status, setStatus] = useState<CallStatus>('idle');
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phone = '+212 6•• ••• ' + patientUuid.slice(-3);

  const startCall = useCallback(() => {
    setStatus('ringing');
    setElapsed(0);
    // Simulate ring → connect after 2s
    setTimeout(() => {
      setStatus('connected');
      timerRef.current = setInterval(() => setElapsed((t) => t + 1), 1000);
    }, 2000);
  }, []);

  const endCall = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    setStatus('ended');
  }, []);

  useEffect(() => {
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  const formatTime = (s: number) => `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;

  const statusLabel: Record<CallStatus, string> = {
    idle: 'Pret',
    ringing: 'Appel en cours...',
    connected: 'En ligne',
    ended: 'Appel termine',
    failed: 'Echec',
  };

  const statusColor: Record<CallStatus, string> = {
    idle: 'var(--t3)',
    ringing: '#FBBF24',
    connected: '#34D399',
    ended: 'var(--t4)',
    failed: '#EF4444',
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 320, background: 'var(--s1)',
          border: '1px solid var(--line)', borderRadius: 16,
          overflow: 'hidden',
          boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '18px 16px 14px',
          background: 'rgba(15,22,35,0.6)',
          borderBottom: '1px solid var(--line)',
          textAlign: 'center',
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: '50%',
            background: 'rgba(52,211,153,0.12)',
            border: '1px solid rgba(52,211,153,0.3)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 10,
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
              stroke="#34D399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>
            </svg>
          </div>
          <div style={{
            fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600,
            color: 'var(--t0)', marginBottom: 4,
          }}>
            Appeler le patient
          </div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)',
            letterSpacing: '0.1em',
          }}>
            {patientUuid.slice(0, 8)}...
          </div>
        </div>

        {/* Body */}
        <div style={{ padding: '16px 16px 12px' }}>
          {/* Phone number */}
          <div style={{
            background: 'var(--s2)', border: '1px solid var(--line)',
            borderRadius: 10, padding: '10px 14px', marginBottom: 12,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="var(--t3)" strokeWidth="2" strokeLinecap="round">
              <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/>
              <line x1="12" y1="18" x2="12.01" y2="18"/>
            </svg>
            <span style={{
              fontFamily: 'var(--f-mono)', fontSize: 14, color: 'var(--t1)',
              letterSpacing: '0.06em',
            }}>
              {phone}
            </span>
          </div>

          {/* Alert context */}
          <div style={{
            fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t3)',
            lineHeight: 1.5, marginBottom: 14,
            padding: '8px 10px', background: 'rgba(239,68,68,0.06)',
            borderRadius: 8, border: '1px solid rgba(239,68,68,0.12)',
          }}>
            {narrative}
          </div>

          {/* Status */}
          <div style={{
            textAlign: 'center', marginBottom: 14,
          }}>
            <span style={{
              fontFamily: 'var(--f-mono)', fontSize: 10,
              letterSpacing: '0.14em', textTransform: 'uppercase',
              color: statusColor[status],
            }}>
              {statusLabel[status]}
            </span>
            {status === 'connected' && (
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 20, fontWeight: 600,
                color: '#34D399', marginTop: 4,
              }}>
                {formatTime(elapsed)}
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8 }}>
            {(status === 'idle' || status === 'ended') && (
              <button
                onClick={startCall}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: 10,
                  background: 'rgba(52,211,153,0.15)', border: '1px solid rgba(52,211,153,0.3)',
                  color: '#34D399', fontFamily: 'var(--f-mono)', fontSize: 11,
                  fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
                  cursor: 'pointer', transition: 'background 0.15s',
                }}
              >
                Appeler
              </button>
            )}
            {(status === 'ringing' || status === 'connected') && (
              <button
                onClick={endCall}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: 10,
                  background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
                  color: '#EF4444', fontFamily: 'var(--f-mono)', fontSize: 11,
                  fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
                  cursor: 'pointer', transition: 'background 0.15s',
                }}
              >
                Raccrocher
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 10,
                background: 'var(--s2)', border: '1px solid var(--line)',
                color: 'var(--t3)', fontFamily: 'var(--f-mono)', fontSize: 11,
                fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
                cursor: 'pointer', transition: 'background 0.15s',
              }}
            >
              Fermer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── drawer ──────────────────────────────────────────────────────────────────

interface AnomalyFeedProps {
  open: boolean;
  onClose: () => void;
}

export function AnomalyFeed({ open, onClose }: AnomalyFeedProps) {
  const { alerts, markAllRead, dismiss } = useAlerts();
  const drawerRef = useRef<HTMLDivElement>(null);
  const [callTarget, setCallTarget] = useState<{ patientUuid: string; narrative: string } | null>(null);

  // Mark all read when drawer opens
  useEffect(() => {
    if (open) markAllRead();
  }, [open, markAllRead]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    if (open) document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    if (open) setTimeout(() => document.addEventListener('mousedown', handler), 0);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,0.45)',
          backdropFilter: 'blur(2px)',
          opacity: open ? 1 : 0,
          pointerEvents: open ? 'auto' : 'none',
          transition: 'opacity 0.25s ease',
        }}
        onClick={onClose}
      />

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label="Alertes temps réel"
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: 380, zIndex: 201,
          background: 'var(--s1)',
          borderLeft: '1px solid var(--line)',
          display: 'flex', flexDirection: 'column',
          transform: open ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: open ? '-20px 0 60px rgba(0,0,0,0.5)' : 'none',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '18px 18px 14px',
          borderBottom: '1px solid var(--line)',
          display: 'flex', alignItems: 'center', gap: 10,
          background: 'rgba(15,22,35,0.5)',
          flexShrink: 0,
        }}>
          {/* Bell icon */}
          <div style={{
            width: 32, height: 32,
            background: 'rgba(239,68,68,0.12)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
              stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>
              <path d="M10 21a2 2 0 0 0 4 0"/>
            </svg>
          </div>

          <div style={{ flex: 1 }}>
            <div style={{
              fontFamily: 'var(--f-display)', fontWeight: 600,
              fontSize: 14, color: 'var(--t0)', letterSpacing: '-0.01em',
            }}>
              Alertes temps réel
            </div>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
              letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 2,
            }}>
              {alerts.length === 0 ? 'Aucune alerte' : `${alerts.length} alerte${alerts.length > 1 ? 's' : ''}`}
            </div>
          </div>

          {/* Close button */}
          <button
            id="anomaly-feed-close"
            onClick={onClose}
            aria-label="Fermer le panneau d'alertes"
            style={{
              width: 28, height: 28, borderRadius: 6,
              background: 'transparent',
              border: '1px solid var(--line)',
              color: 'var(--t3)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'border-color 0.15s, color 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--t2)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--t1)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--line)'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--t3)'; }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Alert list */}
        <div
          className="scroll-hide"
          style={{ flex: 1, overflowY: 'auto', padding: 12 }}
        >
          {alerts.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              height: '100%', gap: 12, padding: 24,
            }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12,
                background: 'var(--s2)',
                border: '1px solid var(--line)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
                  stroke="var(--t4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>
                  <path d="M10 21a2 2 0 0 0 4 0"/>
                </svg>
              </div>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)',
                letterSpacing: '0.1em', textTransform: 'uppercase', textAlign: 'center',
              }}>
                Aucune alerte active
              </div>
              <div style={{
                fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t3)',
                textAlign: 'center', lineHeight: 1.5,
              }}>
                Les alertes critiques s&apos;afficheront ici dès qu&apos;un signe vital franchit un seuil.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {alerts.map((a) => {
                const hr = a.reading?.hr;
                const spo2 = a.reading?.spo2;
                const hrv = a.reading?.hrv;
                return (
                  <div
                    key={a.id}
                    style={{
                      background: 'var(--s0)',
                      border: '1px solid rgba(239,68,68,0.2)',
                      borderLeft: '3px solid #EF4444',
                      borderRadius: 10,
                      padding: '12px 12px 10px',
                      position: 'relative',
                      transition: 'border-color 0.15s',
                    }}
                    onMouseEnter={e => (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(239,68,68,0.45)'}
                    onMouseLeave={e => (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(239,68,68,0.2)'}
                  >
                    {/* Top row: badge + time + dismiss */}
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      marginBottom: 8,
                    }}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '2px 7px', borderRadius: 99,
                        background: 'rgba(239,68,68,0.12)',
                        border: '1px solid rgba(239,68,68,0.3)',
                        fontSize: 9, fontFamily: 'var(--f-mono)',
                        color: '#EF4444', letterSpacing: '0.14em',
                        textTransform: 'uppercase', fontWeight: 700,
                      }}>
                        <span style={{
                          width: 5, height: 5, borderRadius: '50%',
                          background: '#EF4444',
                          boxShadow: '0 0 4px rgba(239,68,68,0.8)',
                          display: 'inline-block',
                        }} />
                        critique
                      </span>
                      <span style={{
                        fontFamily: 'var(--f-mono)', fontSize: 9,
                        color: 'var(--t4)', flex: 1,
                      }}>
                        {relativeTime(a.receivedAt)}
                      </span>
                      {a.patient_uuid && (
                        <button
                          onClick={() => setCallTarget({
                            patientUuid: String(a.patient_uuid),
                            narrative: a.narrative ?? 'Anomalie detectee',
                          })}
                          aria-label="Appeler le patient"
                          title="Appeler le patient"
                          style={{
                            background: 'rgba(52,211,153,0.1)',
                            border: '1px solid rgba(52,211,153,0.25)',
                            borderRadius: 5,
                            color: '#34D399', cursor: 'pointer',
                            padding: '2px 4px', lineHeight: 1,
                            transition: 'background 0.15s, border-color 0.15s',
                          }}
                          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(52,211,153,0.2)'; (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(52,211,153,0.5)'; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(52,211,153,0.1)'; (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(52,211,153,0.25)'; }}
                        >
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>
                          </svg>
                        </button>
                      )}
                      <button
                        onClick={() => dismiss(a.id)}
                        aria-label="Rejeter cette alerte"
                        style={{
                          background: 'transparent', border: 'none',
                          color: 'var(--t4)', cursor: 'pointer',
                          padding: 2, lineHeight: 1,
                          opacity: 0.5, transition: 'opacity 0.15s',
                        }}
                        onMouseEnter={e => (e.currentTarget as HTMLButtonElement).style.opacity = '1'}
                        onMouseLeave={e => (e.currentTarget as HTMLButtonElement).style.opacity = '0.5'}
                      >
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                          <path d="M18 6 6 18M6 6l12 12"/>
                        </svg>
                      </button>
                    </div>

                    {/* Narrative headline */}
                    <div style={{
                      fontFamily: 'var(--f-body)', fontWeight: 600,
                      fontSize: 13, color: 'var(--t0)', lineHeight: 1.4,
                      marginBottom: 8,
                    }}>
                      {a.narrative ?? 'Anomalie détectée'}
                    </div>

                    {/* Subline: patient + vitals chips */}
                    <div style={{
                      display: 'flex', alignItems: 'center',
                      flexWrap: 'wrap', gap: 6,
                    }}>
                      {a.patient_uuid && (
                        <span style={{
                          fontFamily: 'var(--f-mono)', fontSize: 9.5,
                          color: 'var(--t4)', letterSpacing: '0.04em',
                        }}>
                          {String(a.patient_uuid).slice(0, 8)}…
                        </span>
                      )}
                      {typeof hr === 'number' && (
                        <VitalChip label="♥" value={`${Math.round(hr)} bpm`} color="#FF3D71" />
                      )}
                      {typeof spo2 === 'number' && (
                        <VitalChip label="O₂" value={`${Math.round(spo2)}%`} color="#38BDF8" />
                      )}
                      {typeof hrv === 'number' && (
                        <VitalChip label="HRV" value={`${Math.round(hrv)} ms`} color="#A78BFA" />
                      )}
                      {typeof a.score_5m === 'number' && (
                        <span style={{
                          fontFamily: 'var(--f-mono)', fontSize: 9,
                          color: 'var(--t4)', marginLeft: 'auto',
                          letterSpacing: '0.04em',
                        }}>
                          score {a.score_5m.toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer — subtle gradient fade */}
        <div style={{
          height: 1, background: 'var(--line)', flexShrink: 0,
        }} />
        <div style={{
          padding: '10px 18px',
          fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
          letterSpacing: '0.12em', textTransform: 'uppercase', textAlign: 'center',
          background: 'var(--s1)', flexShrink: 0,
        }}>
          Mis à jour en temps réel · WebSocket
        </div>
      </div>

      {/* Call Patient Modal */}
      {callTarget && (
        <CallPatientModal
          patientUuid={callTarget.patientUuid}
          narrative={callTarget.narrative}
          onClose={() => setCallTarget(null)}
        />
      )}
    </>
  );
}
