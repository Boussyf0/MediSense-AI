'use client';
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashPage } from '@/components/dashboard-shell';

type Outcome = 'presented' | 'no_show';

interface Appointment {
  appointment_uuid: string;
  patient_uuid: string;
  patient_name: string | null;
  scheduled_at: string;
  noshow_probability: number | null;
  risk_color: string | null;
  status: string;
  sms_reminders_sent: number;
}

function riskDot(color: string | null) {
  const c = color === 'red' ? '#EF4444' : color === 'orange' ? '#F59E0B' : '#22C55E';
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: c, flexShrink: 0,
    }} />
  );
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

export default function FeedbackPage() {
  const [doctorUuid, setDoctorUuid] = useState('');
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [feedbackMap, setFeedbackMap] = useState<Record<string, Outcome>>({});
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // Fetch doctors for the selector (GET /doctors — accessible to any authenticated user)
  const { data: doctors } = useQuery<Array<{ user_uuid: string; first_name: string; last_name: string; specialty: string | null; display_name: string }>>({
    queryKey: ['doctors-list'],
    queryFn: async () => {
      const { data } = await api.get('/doctors');
      return data as Array<{ user_uuid: string; first_name: string; last_name: string; specialty: string | null; display_name: string }>;
    },
  });

  // Fetch appointments for the selected doctor+date
  const { data: appointments, isLoading, refetch } = useQuery<Appointment[]>({
    queryKey: ['feedback-appointments', doctorUuid, selectedDate],
    queryFn: async () => {
      if (!doctorUuid) return [];
      const { data } = await api.get(
        `/predictions/no-show/batch?doctor_uuid=${doctorUuid}&date=${selectedDate}`,
      );
      return data as Appointment[];
    },
    enabled: !!doctorUuid,
  });

  // Submit feedback mutation — closes the ML feedback loop
  const feedbackMutation = useMutation({
    mutationFn: async ({ appointmentUuid, outcome }: { appointmentUuid: string; outcome: Outcome }) => {
      const { data } = await api.post(`/predictions/no-show/${appointmentUuid}/feedback`, { outcome });
      return { appointmentUuid, outcome, updatedPredictions: (data as { updated_predictions?: number }).updated_predictions ?? 0 };
    },
    onSuccess: (vars) => {
      setFeedbackMap((prev) => ({ ...prev, [vars.appointmentUuid]: vars.outcome }));
      const statusMsg = vars.outcome === 'presented' ? 'Present' : 'Absent';
      const mlMsg = vars.updatedPredictions > 0
        ? ` — ${vars.updatedPredictions} prediction(s) mise a jour`
        : '';
      showToast(`${statusMsg}${mlMsg}`);
      // Refetch to reflect updated probabilities from the ML re-prediction
      refetch();
    },
    onError: () => showToast('Erreur lors de l\'envoi du feedback'),
  });

  const allAppointments = (appointments ?? []).filter(
    (a) => a.status !== 'CANCELLED',
  );

  return (
    <>
      <DashPage
        title="Feedback ML"
        subtitle="Confirmer la presence des patients pour ameliorer les predictions no-show"
      >
        {/* Filters */}
        <div style={{
          display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap',
          alignItems: 'flex-end',
        }}>
          {/* Doctor selector */}
          <div>
            <label style={{
              fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
              letterSpacing: '0.12em', textTransform: 'uppercase',
              display: 'block', marginBottom: 4,
            }}>
              Medecin
            </label>
            <select
              value={doctorUuid}
              onChange={(e) => setDoctorUuid(e.target.value)}
              style={{
                background: 'var(--s2)', border: '1px solid var(--line)',
                borderRadius: 8, padding: '8px 12px', minWidth: 220,
                fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t0)',
                cursor: 'pointer', outline: 'none',
              }}
            >
              <option value="">-- Choisir un medecin --</option>
              {(doctors ?? []).map((d) => (
                <option key={d.user_uuid} value={d.user_uuid}>
                  {d.display_name}
                  {d.specialty ? ` (${d.specialty})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Date picker */}
          <div>
            <label style={{
              fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
              letterSpacing: '0.12em', textTransform: 'uppercase',
              display: 'block', marginBottom: 4,
            }}>
              Date
            </label>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              style={{
                background: 'var(--s2)', border: '1px solid var(--line)',
                borderRadius: 8, padding: '8px 12px',
                fontFamily: 'var(--f-mono)', fontSize: 13, color: 'var(--t0)',
                outline: 'none',
              }}
            />
          </div>

          <button
            onClick={() => refetch()}
            style={{
              padding: '8px 16px', borderRadius: 8,
              background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.3)',
              color: '#A78BFA', fontFamily: 'var(--f-mono)', fontSize: 11,
              fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase',
              cursor: 'pointer',
            }}
          >
            Charger
          </button>
        </div>

        {/* Results */}
        {!doctorUuid ? (
          <div style={{
            textAlign: 'center', padding: 40,
            fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t3)',
          }}>
            Selectionnez un medecin pour afficher les rendez-vous a evaluer.
          </div>
        ) : isLoading ? (
          <div style={{
            textAlign: 'center', padding: 40,
            fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t4)',
            letterSpacing: '0.1em', textTransform: 'uppercase',
          }}>
            Chargement...
          </div>
        ) : allAppointments.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: 40,
            fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t3)',
          }}>
            Aucun rendez-vous a evaluer pour cette date.
          </div>
        ) : (
          <>
            {/* Stats bar */}
            <div style={{
              display: 'flex', gap: 16, marginBottom: 16,
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)',
              letterSpacing: '0.08em',
            }}>
              <span>{allAppointments.length} RDV</span>
              <span>{Object.values(feedbackMap).filter((v) => v === 'presented').length} presents</span>
              <span>{Object.values(feedbackMap).filter((v) => v === 'no_show').length} absents</span>
              <span>
                {allAppointments.length - Object.keys(feedbackMap).length} en attente
              </span>
            </div>

            {/* Appointment cards */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {allAppointments.map((apt) => {
                // Feedback from local state OR from server status (after refetch)
                const fb = feedbackMap[apt.appointment_uuid]
                  ?? (apt.status === 'COMPLETED' ? 'presented' as Outcome : undefined)
                  ?? (apt.status === 'NO_SHOW' ? 'no_show' as Outcome : undefined);
                const prob = apt.noshow_probability;
                return (
                  <div
                    key={apt.appointment_uuid}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '12px 14px',
                      background: fb
                        ? fb === 'presented' ? 'rgba(34,197,94,0.04)' : 'rgba(239,68,68,0.04)'
                        : 'var(--s1)',
                      border: `1px solid ${fb
                        ? fb === 'presented' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'
                        : 'var(--line)'}`,
                      borderRadius: 10,
                      transition: 'all 0.15s',
                    }}
                  >
                    {/* Risk dot */}
                    {riskDot(apt.risk_color ?? null)}

                    {/* Patient info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: 500,
                        color: 'var(--t0)',
                      }}>
                        {apt.patient_name ?? `Patient ${String(apt.patient_uuid).slice(0, 8)}...`}
                      </div>
                      <div style={{
                        fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)',
                        marginTop: 2,
                      }}>
                        {formatDate(apt.scheduled_at)} a {formatTime(apt.scheduled_at)}
                        {typeof prob === 'number' && (
                          <span style={{ marginLeft: 8 }}>
                            risque {Math.round(prob * 100)}%
                          </span>
                        )}
                        {apt.sms_reminders_sent > 0 && (
                          <span style={{ marginLeft: 8, color: '#60A5FA' }}>
                            {apt.sms_reminders_sent} SMS
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Status */}
                    <div style={{
                      fontFamily: 'var(--f-mono)', fontSize: 9,
                      padding: '2px 7px', borderRadius: 5,
                      background: 'var(--s2)', border: '1px solid var(--line)',
                      color: 'var(--t3)', textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                    }}>
                      {apt.status}
                    </div>

                    {/* Feedback buttons */}
                    <div style={{ display: 'flex', gap: 4 }}>
                      {(['presented', 'no_show'] as Outcome[]).map((outcome) => {
                        const active = fb === outcome;
                        const color = outcome === 'presented' ? '#22C55E' : '#EF4444';
                        const label = outcome === 'presented' ? 'Present' : 'Absent';
                        return (
                          <button
                            key={outcome}
                            onClick={() => {
                              if (!fb) {
                                feedbackMutation.mutate({
                                  appointmentUuid: apt.appointment_uuid,
                                  outcome,
                                });
                              }
                            }}
                            disabled={!!fb}
                            style={{
                              padding: '6px 10px', borderRadius: 6,
                              background: active ? `${color}22` : 'transparent',
                              border: `1px solid ${active ? color : 'var(--line)'}`,
                              color: active ? color : fb ? 'var(--t4)' : 'var(--t2)',
                              fontFamily: 'var(--f-mono)', fontSize: 10.5, fontWeight: 600,
                              cursor: fb ? 'default' : 'pointer',
                              opacity: fb && !active ? 0.4 : 1,
                              whiteSpace: 'nowrap',
                              transition: 'all 0.15s',
                            }}
                          >
                            {outcome === 'presented' ? '\u2713' : '\u2717'} {label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </DashPage>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 1000,
          background: '#1f1730', border: '1px solid var(--line)',
          color: '#fff', padding: '10px 16px', borderRadius: 8,
          fontFamily: 'var(--f-mono)', fontSize: 12,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
          {toast}
        </div>
      )}
    </>
  );
}
