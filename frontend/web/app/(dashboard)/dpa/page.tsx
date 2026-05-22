'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/lib/auth';
import { api } from '@/lib/api';
import { DashPage } from '@/components/dashboard-shell';
import { RiskBadge } from '@/components/risk-badge';
import { DashButton } from '@/components/dash-button';
import { IconCalendar, IconSync } from '@/components/icons';

interface BackendAppointmentPrediction {
  appointment_uuid: string;
  patient_uuid: string;
  patient_name?: string | null;
  scheduled_at: string;
  noshow_probability: number | null;
  risk_color: 'green' | 'orange' | 'red' | null;
  status: string;
  sms_reminders_sent: number;
}

type RiskLevel = 'safe' | 'warn' | 'danger' | null;

function today() {
  return new Date().toISOString().slice(0, 10);
}

function riskFromColor(color: BackendAppointmentPrediction['risk_color']): RiskLevel {
  if (color === 'green') return 'safe';
  if (color === 'orange') return 'warn';
  if (color === 'red') return 'danger';
  return null;
}

function patientLabel(item: BackendAppointmentPrediction): string {
  const name = (item.patient_name ?? '').trim();
  return name ? name : `Patient ${item.patient_uuid.slice(0, 8)}`;
}

export default function DpaPage() {
  const { user } = useAuthStore();
  const [date, setDate] = useState(today());

  const { data, isLoading, isError, refetch, isFetching } = useQuery<BackendAppointmentPrediction[]>({
    queryKey: ['dpa-hub', date, user?.uuid],
    queryFn: async () => {
      const params = new URLSearchParams({ date });
      if (user?.uuid) params.set('doctor_uuid', user.uuid);
      const { data } = await api.get(`/predictions/no-show/batch?${params}`);
      return Array.isArray(data) ? data : [];
    },
    enabled: !!user?.uuid,
  });

  return (
    <DashPage
      breadcrumb="dpa"
      title="Résumés DPA"
      subtitle="Entrée rapide vers les résumés patients du jour"
      actions={
        <>
          <label style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '7px 10px', borderRadius: 8,
            background: 'var(--s2)', color: 'var(--t0)',
            border: '1px solid var(--line-strong)',
            fontFamily: 'var(--f-body)', fontSize: 12.5, cursor: 'pointer',
          }}>
            <IconCalendar size={13} stroke={2} />
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              style={{
                background: 'transparent', border: 'none', outline: 'none',
                color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12, colorScheme: 'dark',
              }}
            />
          </label>
          <DashButton
            kind="solid"
            small
            icon={<IconSync size={13} stroke={2} />}
            onClick={() => refetch()}
            loading={isFetching && !isLoading}
          >
            Actualiser
          </DashButton>
        </>
      }
    >
      {!user?.uuid && (
        <div style={{ color: '#EF4444', fontSize: 13 }}>
          Utilisateur non chargé — reconnectez-vous.
        </div>
      )}

      {isLoading && (
        <div style={panelStyle}>Chargement…</div>
      )}

      {isError && (
        <div style={{ ...panelStyle, borderColor: 'rgba(239,68,68,0.45)', color: '#EF4444' }}>
          Impossible de charger les rendez-vous pour générer les DPA.
        </div>
      )}

      {!isLoading && !isError && (data ?? []).length === 0 && (
        <div style={panelStyle}>
          Aucun rendez-vous trouvé pour cette date.
        </div>
      )}

      {!isLoading && !isError && (data ?? []).length > 0 && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12,
        }}>
          {(data ?? []).map((item) => (
            <div key={item.appointment_uuid} style={cardStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ color: 'var(--t0)', fontWeight: 600, fontSize: 13 }}>
                    {patientLabel(item)}
                  </div>
                  <RiskBadge level={riskFromColor(item.risk_color)} prob={item.noshow_probability ?? undefined} />
                </div>
              <div style={{ color: 'var(--t2)', fontSize: 12.5, marginBottom: 12 }}>
                {new Date(item.scheduled_at).toLocaleString('fr-FR')} · {item.status.toLowerCase()}
              </div>
              <Link
                href={`/patients/${item.patient_uuid}/dpa`}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: 'var(--ai-grad)',
                  color: '#fff',
                  textDecoration: 'none',
                  fontSize: 12.5,
                  fontWeight: 600,
                }}
              >
                Ouvrir le résumé DPA
              </Link>
            </div>
          ))}
        </div>
      )}
    </DashPage>
  );
}

const panelStyle: React.CSSProperties = {
  background: 'var(--s1)',
  border: '1px solid var(--line)',
  borderRadius: 14,
  padding: 20,
  color: 'var(--t2)',
  fontSize: 13.5,
};

const cardStyle: React.CSSProperties = {
  background: 'var(--s1)',
  border: '1px solid var(--line)',
  borderRadius: 14,
  padding: 14,
};
