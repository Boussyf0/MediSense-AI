'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashPage } from '@/components/dashboard-shell';

interface DetailedHealth {
  uptime_unix: number;
  services: Record<string, string>;
  models: {
    lstm_anomaly: { path: string; present: boolean; size_bytes: number };
    noshow_mlflow: string;
  };
  kafka: { brokers: string; topic: string };
  tables: Record<string, number | null>;
  env: { app_env: string; llm_provider: string };
}

function pill(ok: boolean) {
  return {
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: 12,
    fontSize: 12,
    fontWeight: 600,
    background: ok ? '#16341c' : '#3a1d1d',
    color: ok ? '#7ee2a3' : '#ff8b8b',
    border: `1px solid ${ok ? '#2c6c41' : '#7a2c2c'}`,
  } as const;
}

const card: React.CSSProperties = {
  background: 'var(--s1)',
  border: '1px solid var(--bd)',
  borderRadius: 10,
  padding: 18,
  marginBottom: 16,
};

const row: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  padding: '6px 0',
  borderBottom: '1px solid var(--bd)',
  fontSize: 14,
};

function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export default function SystemPage() {
  const { data, isLoading, error, refetch } = useQuery<DetailedHealth>({
    queryKey: ['system-health'],
    queryFn: async () => (await api.get('/health/detailed')).data,
    refetchInterval: 30_000,
  });

  return (
    <DashPage title="System Health" subtitle="Live snapshot of MediSense services and ML artefacts">
      <div style={{ padding: '0 4px' }}>
        {isLoading && <div style={{ opacity: 0.6 }}>Loading…</div>}
        {error && <div style={{ color: '#ff8b8b' }}>Failed to load: {String(error)}</div>}
        {data && (
          <>
            <div style={card}>
              <h3 style={{ marginTop: 0 }}>Services</h3>
              {Object.entries(data.services).map(([k, v]) => (
                <div key={k} style={row}>
                  <span>{k}</span>
                  <span style={pill(v === 'ok')}>{v}</span>
                </div>
              ))}
            </div>

            <div style={card}>
              <h3 style={{ marginTop: 0 }}>Models</h3>
              <div style={row}>
                <span>LSTM anomaly artefact</span>
                <span style={pill(data.models.lstm_anomaly.present)}>
                  {data.models.lstm_anomaly.present
                    ? fmtBytes(data.models.lstm_anomaly.size_bytes)
                    : 'missing'}
                </span>
              </div>
              <div style={{ ...row, color: 'var(--tx-2)', fontFamily: 'monospace', fontSize: 12 }}>
                <span>{data.models.lstm_anomaly.path}</span>
              </div>
              <div style={row}>
                <span>No-show MLflow registry</span>
                <span>{data.models.noshow_mlflow}</span>
              </div>
            </div>

            <div style={card}>
              <h3 style={{ marginTop: 0 }}>IoT / Kafka</h3>
              <div style={row}>
                <span>Brokers</span>
                <span style={pill(!data.kafka.brokers.startsWith('('))}>{data.kafka.brokers}</span>
              </div>
              <div style={row}>
                <span>Topic</span>
                <code>{data.kafka.topic}</code>
              </div>
            </div>

            <div style={card}>
              <h3 style={{ marginTop: 0 }}>Tables</h3>
              {Object.entries(data.tables).map(([k, v]) => (
                <div key={k} style={row}>
                  <span>{k}</span>
                  <span>{v === null ? '—' : v.toLocaleString()}</span>
                </div>
              ))}
            </div>

            <div style={card}>
              <h3 style={{ marginTop: 0 }}>Environment</h3>
              <div style={row}>
                <span>App env</span>
                <span>{data.env.app_env}</span>
              </div>
              <div style={row}>
                <span>LLM provider</span>
                <span>{data.env.llm_provider}</span>
              </div>
            </div>

            <button
              onClick={() => refetch()}
              style={{
                marginTop: 8,
                padding: '8px 16px',
                background: 'var(--accent)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
              }}
            >
              Refresh now
            </button>
          </>
        )}
      </div>
    </DashPage>
  );
}
