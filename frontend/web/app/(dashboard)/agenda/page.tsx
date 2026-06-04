'use client';
import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/lib/auth';
import { api } from '@/lib/api';
import { RiskBadge } from '@/components/risk-badge';
import { StatusBadge } from '@/components/status-badge';
import { DashButton } from '@/components/dash-button';
import { DashPage } from '@/components/dashboard-shell';
import { IconCalendar, IconSync, IconSend, IconChevron, IconDoc } from '@/components/icons';

type RiskLevel = 'safe' | 'warn' | 'danger' | null;
type SmsStatus = 'pending' | 'sent' | 'failed' | 'skipped';
type FeedbackValue = 'presented' | 'no_show';

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

interface AppointmentRow {
  appointment_uuid: string;
  patient_uuid: string;
  patient_name: string;
  time: string;
  motif: string;
  no_show_prob: number;
  no_show_level: RiskLevel;
  sms_status: SmsStatus;
  status: string;
}

// ── Patient appointment types (from GET /appointments) ────────────────────────
interface PatientAppointmentItem {
  appointment_uuid: string;
  scheduled_at: string;
  appointment_time: string;
  appointment_type: string;
  doctor_name: string;
  status: string;
  noshow_probability: number | null;
  risk_color: 'green' | 'orange' | 'red' | null;
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    SCHEDULED: 'Planifié', CONFIRMED: 'Confirmé',
    CANCELLED: 'Annulé', COMPLETED: 'Terminé', NO_SHOW: 'Absent',
  };
  return map[s] ?? s.toLowerCase().replaceAll('_', ' ');
}
function statusColor(s: string): string {
  if (s === 'CONFIRMED' || s === 'COMPLETED') return '#22C55E';
  if (s === 'NO_SHOW') return '#EF4444';
  if (s === 'CANCELLED') return '#64748B';
  return '#A78BFA';
}

function PatientAgendaView({ date, setDate }: { date: string; setDate: (d: string) => void }) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery<PatientAppointmentItem[]>({
    queryKey: ['patient-appointments', date],
    queryFn: async () => {
      const { data } = await api.get(`/appointments?date=${date}`);
      return Array.isArray(data) ? data : [];
    },
    enabled: !!date,
  });

  const upcoming = data ?? [];

  return (
    <DashPage
      breadcrumb={`mes rendez-vous · ${formatFR(date)}`}
      title="Mes rendez-vous"
      subtitle={`${upcoming.length} rendez-vous · ${formatFR(date)}`}
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
                color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12,
                colorScheme: 'dark',
              }}
            />
          </label>
          <DashButton
            kind="solid" small
            icon={<IconSync size={13} stroke={2} />}
            onClick={() => refetch()}
            loading={isFetching && !isLoading}
          >
            Actualiser
          </DashButton>
        </>
      }
    >
      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          display: 'grid', gridTemplateColumns: '90px 1fr 160px 130px 110px',
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 500,
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Heure</div>
          <div>Médecin</div>
          <div>Type</div>
          <div>Statut</div>
          <div>Risque</div>
        </div>

        {isLoading && Array.from({ length: 4 }).map((_, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '90px 1fr 160px 130px 110px',
            padding: '14px 18px', alignItems: 'center',
            borderBottom: '1px solid var(--line)',
          }}>
            {[60, 140, 120, 100, 80].map((w, j) => (
              <div key={j} style={{
                height: 13, width: w, borderRadius: 4,
                background: 'linear-gradient(90deg, var(--s2) 25%, var(--s3) 50%, var(--s2) 75%)',
                backgroundSize: '400px 100%', animation: 'shimmer 1.5s infinite',
              }} />
            ))}
          </div>
        ))}

        {!isLoading && isError && (
          <div style={{ padding: 40, textAlign: 'center', color: '#EF4444', fontSize: 13 }}>
            Erreur de chargement. Vérifiez la connexion.
          </div>
        )}

        {!isLoading && !isError && upcoming.length === 0 && (
          <div style={{ padding: 56, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
            <div style={{ fontSize: 28, marginBottom: 12, opacity: 0.5 }}>
              <IconDoc size={32} stroke={1.5} />
            </div>
            Aucun rendez-vous pour cette date
          </div>
        )}

        {!isLoading && upcoming.map((apt, i) => {
          const color = statusColor(apt.status);
          const last = i === upcoming.length - 1;
          return (
            <div key={apt.appointment_uuid} style={{
              display: 'grid', gridTemplateColumns: '90px 1fr 160px 130px 110px',
              padding: '14px 18px', alignItems: 'center',
              borderBottom: last ? 'none' : '1px solid var(--line)',
            }}>
              <div style={{ fontFamily: 'var(--f-display)', fontSize: 15, fontWeight: 600, color: 'var(--t0)' }}>
                {apt.appointment_time ?? formatHour(apt.scheduled_at)}
              </div>
              <div>
                <div style={{ fontSize: 13.5, color: 'var(--t0)', fontWeight: 500 }}>
                  {apt.doctor_name}
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>
                  {formatFR(apt.scheduled_at.slice(0, 10))}
                </div>
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--t2)' }}>
                {apt.appointment_type.replaceAll('_', ' ')}
              </div>
              <div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  padding: '3px 10px', borderRadius: 99,
                  background: `${color}18`, border: `1px solid ${color}44`,
                  color, fontFamily: 'var(--f-mono)', fontSize: 10.5, fontWeight: 600,
                }}>
                  <span style={{ width: 5, height: 5, borderRadius: 99, background: color }} />
                  {statusLabel(apt.status)}
                </span>
              </div>
              <div>
                <RiskBadge
                  level={apt.risk_color === 'green' ? 'safe' : apt.risk_color === 'orange' ? 'warn' : apt.risk_color === 'red' ? 'danger' : null}
                  prob={apt.noshow_probability ?? 0}
                />
              </div>
            </div>
          );
        })}
      </div>
    </DashPage>
  );
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function formatFR(iso: string) {
  try {
    return new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR', {
      day: 'numeric', month: 'long', year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function formatHour(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '—';
  }
}

function riskFromColor(color: BackendAppointmentPrediction['risk_color']): RiskLevel {
  if (color === 'green') return 'safe';
  if (color === 'orange') return 'warn';
  if (color === 'red') return 'danger';
  return null;
}

function patientLabel(pred: BackendAppointmentPrediction): string {
  const name = (pred.patient_name ?? '').trim();
  return name ? name : `Patient ${pred.patient_uuid.slice(0, 8)}`;
}

function mapPredictionToRow(pred: BackendAppointmentPrediction): AppointmentRow {
  return {
    appointment_uuid: pred.appointment_uuid,
    patient_uuid: pred.patient_uuid,
    patient_name: patientLabel(pred),
    time: formatHour(pred.scheduled_at),
    motif: pred.status.replaceAll('_', ' ').toLowerCase(),
    no_show_prob: pred.noshow_probability ?? 0,
    no_show_level: riskFromColor(pred.risk_color),
    sms_status: pred.sms_reminders_sent > 0 ? 'sent' : 'pending',
    status: pred.status,
  };
}

const COL_TEMPLATE = '90px 1fr 180px 120px 130px 110px 30px';

export default function AgendaPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const isSecretary = user?.role === 'secretary';
  const isPatient = user?.role === 'patient';
  const isDoctor = user?.role === 'doctor';

  const [date, setDate] = useState(today());
  const [selectedDoctorUuid, setSelectedDoctorUuid] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const [feedbackByAppointment, setFeedbackByAppointment] = useState<Record<string, FeedbackValue>>({});

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // Fetch doctors list for secretary role
  const { data: doctors } = useQuery<Array<{ user_uuid: string; display_name: string; specialty: string | null }>>({
    queryKey: ['doctors-list'],
    queryFn: async () => {
      const { data } = await api.get('/doctors');
      return data as Array<{ user_uuid: string; display_name: string; specialty: string | null }>;
    },
    enabled: isSecretary,
  });

  // Doctor UUID: own UUID for doctors, selected UUID for secretary
  const doctorUuid = isDoctor ? user?.uuid : selectedDoctorUuid;

  const { data, isLoading, isError, refetch, isFetching } = useQuery<BackendAppointmentPrediction[]>({
    queryKey: ['no-show', date, doctorUuid],
    queryFn: async () => {
      const params = new URLSearchParams({ date });
      if (doctorUuid) params.set('doctor_uuid', doctorUuid);
      const { data } = await api.get(`/predictions/no-show/batch?${params}`);
      return Array.isArray(data) ? data : [];
    },
    enabled: !!date && !!doctorUuid,
  });

  const smsMutation = useMutation({
    mutationFn: async (appointmentUuid: string) => {
      const { data } = await api.post(`/crm/sms/send/${appointmentUuid}`);
      return data;
    },
    onSuccess: () => {
      showToast('SMS envoyé avec succès');
      queryClient.invalidateQueries({ queryKey: ['no-show'] });
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      showToast(detail ? `Échec de l'envoi: ${detail}` : "Échec de l'envoi SMS");
    },
  });

  const dispatchMutation = useMutation({
    mutationFn: async () => {
      if (!doctorUuid) throw new Error('doctor_uuid manquant');
      const { data } = await api.post(
        '/predictions/no-show/reminders/dispatch',
        null,
        { params: { doctor_uuid: doctorUuid, date } },
      );
      return data;
    },
    onSuccess: (d) => {
      showToast(`${(d as { sent?: number }).sent ?? 0} SMS envoyés`);
      queryClient.invalidateQueries({ queryKey: ['no-show'] });
    },
    onError: () => showToast("Erreur lors de l'envoi groupé"),
  });

  const feedbackMutation = useMutation({
    mutationFn: async ({ appointmentUuid, outcome }: { appointmentUuid: string; outcome: FeedbackValue }) => {
      const { data } = await api.post(`/predictions/no-show/${appointmentUuid}/feedback`, { outcome });
      return data;
    },
    onSuccess: (_data, vars) => {
      setFeedbackByAppointment((prev) => ({ ...prev, [vars.appointmentUuid]: vars.outcome }));
      showToast('Feedback enregistré');
    },
    onError: () => showToast('Erreur feedback'),
  });

  const appointments = useMemo(
    () => (data ?? []).map(mapPredictionToRow),
    [data],
  );

  const counts = useMemo(
    () => appointments.reduce(
      (acc, apt) => {
        if (apt.no_show_level === 'safe') acc.safe += 1;
        if (apt.no_show_level === 'warn') acc.warn += 1;
        if (apt.no_show_level === 'danger') acc.danger += 1;
        if (apt.sms_status === 'sent') acc.sms_sent += 1;
        return acc;
      },
      { safe: 0, warn: 0, danger: 0, sms_sent: 0 },
    ),
    [appointments],
  );

  const toCallOrText = counts.danger + counts.warn;
  const totalRdv = appointments.length;

  // Patients see their own appointments — different view entirely.
  // Placed after every hook call so the hooks order stays stable across renders.
  if (isPatient) return <PatientAgendaView date={date} setDate={setDate} />;

  return (
    <DashPage
      breadcrumb={`agenda · ${formatFR(date)}`}
      title="Agenda intelligent"
      subtitle={`Prédiction no-show · ${totalRdv} rendez-vous`}
      actions={
        <>
          {isSecretary && (
            <select
              value={selectedDoctorUuid}
              onChange={(e) => setSelectedDoctorUuid(e.target.value)}
              style={{
                background: 'var(--s2)', border: '1px solid var(--line-strong)',
                borderRadius: 8, padding: '7px 10px', minWidth: 200,
                fontFamily: 'var(--f-body)', fontSize: 12.5, color: 'var(--t0)',
                cursor: 'pointer', outline: 'none',
              }}
            >
              <option value="">-- Choisir un medecin --</option>
              {(doctors ?? []).map((d) => (
                <option key={d.user_uuid} value={d.user_uuid}>
                  {d.display_name}{d.specialty ? ` (${d.specialty})` : ''}
                </option>
              ))}
            </select>
          )}
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
                color: 'var(--t0)', fontFamily: 'var(--f-mono)', fontSize: 12,
                colorScheme: 'dark',
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
          {isSecretary && (
            <DashButton
              kind="gradient"
              small
              icon={<IconSend size={13} stroke={2} />}
              onClick={() => dispatchMutation.mutate()}
              loading={dispatchMutation.isPending}
              disabled={toCallOrText === 0 || !doctorUuid}
            >
              SMS de rappel ({toCallOrText})
            </DashButton>
          )}
        </>
      }
    >
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 24, zIndex: 9999,
          background: 'var(--s2)', border: '1px solid var(--line-strong)',
          borderRadius: 10, padding: '10px 18px',
          color: 'var(--t0)', fontSize: 13, fontWeight: 500,
          animation: 'slide-down 0.3s ease',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}>
          {toast}
        </div>
      )}

      {!doctorUuid && !isSecretary && (
        <div style={{ marginBottom: 16, color: '#EF4444', fontSize: 13 }}>
          Utilisateur non chargé — reconnectez-vous.
        </div>
      )}

      <div style={{ display: 'flex', gap: 14, marginBottom: 20 }}>
        <StatCard count={counts.safe} color="#22C55E" glow="rgba(34,197,94,0.55)" label="Faible" sublabel="probabilité &lt; 20%" />
        <StatCard count={counts.warn} color="#F97316" glow="rgba(249,115,22,0.55)" label="Modéré" sublabel="20–40%" />
        <StatCard count={counts.danger} color="#EF4444" glow="rgba(239,68,68,0.55)" label="Élevé" sublabel="&gt; 40%" />
        <StatCard count={counts.sms_sent} color="#A78BFA" glow="rgba(167,139,250,0.55)" label="SMS env" sublabel="rappels envoyés" />
      </div>

      <div style={{
        background: 'var(--s1)', border: '1px solid var(--line)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        <div style={{
          display: 'grid', gridTemplateColumns: COL_TEMPLATE,
          padding: '11px 18px', background: 'var(--s2)',
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 500,
          borderBottom: '1px solid var(--line)',
        }}>
          <div>Heure</div>
          <div>Patient</div>
          <div>Statut RDV</div>
          <div>No-show</div>
          <div>Rappel</div>
          <div>Action</div>
          <div />
        </div>

        {isLoading && Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)}

        {!isLoading && isError && (
          <div style={{ padding: 40, textAlign: 'center', color: '#EF4444', fontSize: 13 }}>
            Erreur de chargement. Vérifiez la connexion API.
          </div>
        )}

        {!isLoading && !isError && !doctorUuid && isSecretary && (
          <div style={{ padding: 56, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
            Selectionnez un medecin pour afficher l&apos;agenda.
          </div>
        )}

        {!isLoading && !isError && !!doctorUuid && appointments.length === 0 && (
          <div style={{ padding: 56, textAlign: 'center', color: 'var(--t3)', fontSize: 13 }}>
            <div style={{ fontSize: 28, marginBottom: 12, opacity: 0.6 }}>—</div>
            Aucun rendez-vous pour cette date
          </div>
        )}

        {!isLoading && appointments.map((apt, i) => (
          <AppointmentRow
            key={apt.appointment_uuid}
            apt={apt}
            last={i === appointments.length - 1}
            isSecretary={isSecretary}
            feedback={feedbackByAppointment[apt.appointment_uuid]}
            onSms={() => smsMutation.mutate(apt.appointment_uuid)}
            smsPending={smsMutation.isPending && smsMutation.variables === apt.appointment_uuid}
            onFeedback={(outcome) => feedbackMutation.mutate({ appointmentUuid: apt.appointment_uuid, outcome })}
            onOpen={() => router.push(`/agenda/${apt.appointment_uuid}/brief`)}
          />
        ))}
      </div>
    </DashPage>
  );
}

function StatCard({
  count, color, glow, label, sublabel,
}: { count: number; color: string; glow: string; label: string; sublabel: string }) {
  return (
    <div style={{
      flex: 1,
      background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
      padding: '18px 20px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span style={{ width: 8, height: 8, borderRadius: 99, background: color, boxShadow: `0 0 8px ${glow}` }} />
        <span style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>{label}</span>
      </div>
      <div style={{
        fontFamily: 'var(--f-display)', fontSize: 36, fontWeight: 600,
        color: 'var(--t0)', lineHeight: 1, letterSpacing: '-0.02em',
      }}>
        {count}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--t2)', marginTop: 6 }}>{sublabel}</div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: COL_TEMPLATE,
      padding: '13px 18px', alignItems: 'center',
      borderBottom: '1px solid var(--line)',
    }}>
      {[60, 140, 120, 90, 110, 80, 14].map((w, i) => (
        <div key={i} style={{
          height: 14, width: w, borderRadius: 4,
          background: 'linear-gradient(90deg, var(--s2) 25%, var(--s3) 50%, var(--s2) 75%)',
          backgroundSize: '400px 100%', animation: 'shimmer 1.5s infinite',
        }} />
      ))}
    </div>
  );
}

function AppointmentRow({
  apt,
  last,
  isSecretary,
  feedback,
  onSms,
  smsPending,
  onFeedback,
  onOpen,
}: {
  apt: AppointmentRow;
  last: boolean;
  isSecretary: boolean;
  feedback?: FeedbackValue;
  onSms: () => void;
  smsPending: boolean;
  onFeedback: (v: FeedbackValue) => void;
  onOpen: () => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onOpen}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'grid', gridTemplateColumns: COL_TEMPLATE,
        padding: '13px 18px', alignItems: 'center',
        borderBottom: last ? 'none' : '1px solid var(--line)',
        background: hovered ? 'rgba(99,102,241,0.06)' : 'transparent',
        cursor: 'pointer', transition: 'background .14s',
      }}
    >
      <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 500, color: 'var(--t0)' }}>
        {apt.time}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>{apt.patient_name}</div>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>
          uid · {apt.patient_uuid.slice(0, 8)}
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--t2)', textTransform: 'lowercase' }}>
        {apt.motif}
      </div>
      <div><RiskBadge level={apt.no_show_level} prob={apt.no_show_prob} /></div>
      <div>
        <StatusBadge
          tone={apt.sms_status === 'sent' ? 'sent' : 'pending'}
          label={apt.sms_status === 'sent' ? 'Rappel envoyé' : 'En attente'}
          pulse={apt.sms_status !== 'sent'}
        />
      </div>
      <div onClick={(e) => e.stopPropagation()}>
        {isSecretary ? (
          <SecretaryFeedback current={feedback} onPick={onFeedback} />
        ) : (
          <SmsAction status={apt.sms_status} pending={smsPending} onSend={onSms} />
        )}
      </div>
      <div style={{ textAlign: 'right', color: 'var(--t3)' }}>
        <IconChevron size={14} stroke={2} />
      </div>
    </div>
  );
}

function SmsAction({
  status, pending, onSend,
}: { status: SmsStatus; pending: boolean; onSend: () => void }) {
  if (status === 'sent') {
    return (
      <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: '#22C55E' }}>
        ✓ envoyé
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <button
        onClick={onSend}
        disabled={pending}
        style={{
          padding: '4px 9px', borderRadius: 6,
          background: 'rgba(239,68,68,0.10)',
          border: '1px solid rgba(239,68,68,0.40)',
          color: '#EF4444', fontFamily: 'var(--f-mono)', fontSize: 11, fontWeight: 600,
          cursor: pending ? 'default' : 'pointer',
        }}
      >
        {pending ? '…' : 'Réessayer'}
      </button>
    );
  }
  return (
    <button
      onClick={onSend}
      disabled={pending}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 5,
        padding: '4px 9px', borderRadius: 6,
        background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.30)',
        color: '#A78BFA', fontFamily: 'var(--f-body)', fontSize: 11, fontWeight: 600,
        cursor: pending ? 'default' : 'pointer',
      }}
    >
      {pending ? (
        <span style={{
          width: 10, height: 10, borderRadius: '50%',
          border: '1.5px solid rgba(167,139,250,0.3)', borderTopColor: '#A78BFA',
          animation: 'spin 0.8s linear infinite',
        }} />
      ) : (
        <IconSend size={11} stroke={2} />
      )}
      Envoyer
    </button>
  );
}

function SecretaryFeedback({
  current, onPick,
}: { current?: FeedbackValue; onPick: (fb: FeedbackValue) => void }) {
  const opts: Array<{ key: FeedbackValue; label: string; color: string }> = [
    { key: 'presented', label: '✓ présenté', color: '#22C55E' },
    { key: 'no_show', label: '✗ absent', color: '#EF4444' },
  ];
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {opts.map((o) => {
        const active = current === o.key;
        return (
          <button
            key={o.key}
            onClick={() => onPick(o.key)}
            title={o.label}
            style={{
              padding: '4px 8px', borderRadius: 6,
              background: active ? `${o.color}22` : 'transparent',
              border: `1px solid ${active ? o.color : 'var(--line)'}`,
              color: active ? o.color : 'var(--t3)',
              fontFamily: 'var(--f-mono)', fontSize: 10.5, fontWeight: 600,
              cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
