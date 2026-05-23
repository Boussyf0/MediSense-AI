'use client';
import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { alertWs, type AlertPayload } from '@/lib/ws';
import { useAuthStore } from '@/lib/auth';
import { AnomalyFeed } from './anomaly-feed';

type AlertItem = AlertPayload & { id: string; receivedAt: number };

interface AlertsCtx {
  alerts: AlertItem[];
  unread: number;
  markAllRead: () => void;
  dismiss: (id: string) => void;
  isFeedOpen: boolean;
  openFeed: () => void;
  closeFeed: () => void;
}

const Ctx = createContext<AlertsCtx>({
  alerts: [],
  unread: 0,
  markAllRead: () => {},
  dismiss: () => {},
  isFeedOpen: false,
  openFeed: () => {},
  closeFeed: () => {},
});

export const useAlerts = () => useContext(Ctx);

const TOAST_TTL_MS = 8000;

export function AlertsProvider({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [toast, setToast] = useState<AlertItem | null>(null);
  const [isFeedOpen, setIsFeedOpen] = useState(false);

  const openFeed = useCallback(() => setIsFeedOpen(true), []);
  const closeFeed = useCallback(() => setIsFeedOpen(false), []);

  const dismiss = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const markAllRead = useCallback(() => setUnread(0), []);

  useEffect(() => {
    if (!user || !token) return;
    if (user.role !== 'doctor' && user.role !== 'admin' && user.role !== 'secretary') return;

    const off = alertWs.on((data) => {
      const item: AlertItem = {
        ...data,
        id: `${data.ts ?? Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        receivedAt: Date.now(),
      };
      setAlerts((prev) => [item, ...prev].slice(0, 50));
      setUnread((n) => n + 1);
      setToast(item);
      setTimeout(() => setToast((t) => (t?.id === item.id ? null : t)), TOAST_TTL_MS);
    });

    alertWs.connect(user.role, token);
    return () => {
      off();
      alertWs.disconnect();
    };
  }, [user, token]);

  return (
    <Ctx.Provider value={{ alerts, unread, markAllRead, dismiss, isFeedOpen, openFeed, closeFeed }}>
      {children}
      {toast && (
        <div
          role="alert"
          aria-live="polite"
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 1000,
            background: '#1f1730',
            border: '1px solid #c2185b',
            borderLeft: '4px solid #ff3d71',
            color: '#fff',
            padding: '14px 18px',
            borderRadius: 8,
            minWidth: 280,
            maxWidth: 380,
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            fontFamily: 'inherit',
          }}
        >
          <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 4 }}>
            CRITIQUE · {new Date(toast.receivedAt).toLocaleTimeString()}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, lineHeight: 1.35 }}>
            {toast.narrative ?? 'Anomalie détectée'}
          </div>
          <div style={{ fontSize: 12, opacity: 0.75 }}>
            Patient {String(toast.patient_uuid ?? '').slice(0, 8)}…
            {typeof toast.score_5m === 'number' && (
              <span> · score {toast.score_5m.toFixed(2)}</span>
            )}
          </div>
          <button
            onClick={() => setToast(null)}
            style={{
              position: 'absolute',
              top: 6,
              right: 8,
              background: 'transparent',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              fontSize: 18,
              opacity: 0.6,
            }}
            aria-label="Dismiss alert"
          >
            ×
          </button>
        </div>
      )}
      <AnomalyFeed open={isFeedOpen} onClose={closeFeed} />
    </Ctx.Provider>
  );
}
