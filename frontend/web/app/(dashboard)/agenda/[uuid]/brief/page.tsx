'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { DashPage } from '@/components/dashboard-shell';
import { DashButton } from '@/components/dash-button';
import { IconBack, IconHeart, IconActivity, IconChat } from '@/components/icons';
import { RiskBadge } from '@/components/risk-badge';

interface BriefData {
  appointment_uuid: string;
  scheduled_at: string;
  patient: {
    patient_uuid: string;
    display_name?: string;
    age?: number;
    sex?: string;
    chronic_conditions: string[];
  };
  vitals: {
    hr?: number;
    spo2?: number;
    hrv?: number;
    measured_at?: string;
    samples_24h: number;
  };
  anomaly: {
    score_5m?: number;
    score_60m?: number;
    alert_critical: boolean;
    trend_elevated: boolean;
    narrative?: string;
  };
  recent_symptoms: Array<{
    content: string;
    created_at: string;
  }>;
  noshow: {
    probability?: number;
    risk_color?: 'green' | 'orange' | 'red';
  };
  generated_at: string;
}

export default function DoctorBriefPage({ params }: { params: Promise<{ uuid: string }> }) {
  const { uuid } = use(params);
  const router = useRouter();

  const { data, isLoading, isError } = useQuery<BriefData>({
    queryKey: ['doctor-brief', uuid],
    queryFn: async () => {
      const { data } = await api.get(`/doctor/agenda/${uuid}/brief`);
      return data;
    },
  });

  if (isLoading) {
    return (
      <DashPage breadcrumb="agenda › chargement…" title="Brief de consultation">
        <div style={{ display: 'flex', gap: 16, flexDirection: 'column' }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{
              height: 120, borderRadius: 14,
              background: 'linear-gradient(90deg, var(--s1) 25%, var(--s2) 50%, var(--s1) 75%)',
              backgroundSize: '400px 100%', animation: 'shimmer 1.5s infinite',
            }} />
          ))}
        </div>
      </DashPage>
    );
  }

  if (isError || !data) {
    return (
      <DashPage
        breadcrumb="agenda › erreur"
        title="Brief de consultation"
        actions={
          <DashButton kind="ghost" small icon={<IconBack size={13} />} onClick={() => router.back()}>
            Retour
          </DashButton>
        }
      >
        <div style={{ padding: 40, textAlign: 'center', color: '#EF4444', fontSize: 13 }}>
          Impossible de charger le brief de consultation.
        </div>
      </DashPage>
    );
  }

  const { patient, vitals, anomaly, recent_symptoms, noshow } = data;
  const name = patient.display_name || `Patient ${patient.patient_uuid.slice(0, 8)}`;
  
  const noShowLevel = noshow.risk_color === 'green' ? 'safe' : noshow.risk_color === 'orange' ? 'warn' : noshow.risk_color === 'red' ? 'danger' : null;

  return (
    <DashPage
      breadcrumb={`agenda › brief pré-consultation`}
      title={name}
      subtitle={`${patient.age ? `${patient.age} ans` : 'Âge inconnu'} · ${patient.sex === 'M' ? 'Homme' : patient.sex === 'F' ? 'Femme' : 'Sexe inconnu'}`}
      actions={
        <>
          <DashButton kind="ghost" small icon={<IconBack size={13} />} onClick={() => router.back()}>
            Retour agenda
          </DashButton>
          <DashButton kind="gradient" small onClick={() => router.push(`/patients/${patient.patient_uuid}/dpa`)}>
            Démarrer la consultation
          </DashButton>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, alignItems: 'start' }}>
        
        {/* Left Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Patient Info & No-Show */}
          <div style={{
            background: 'var(--s1)', borderRadius: 16, border: '1px solid var(--line)', padding: 20,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Profil Patient
              </div>
              <RiskBadge level={noShowLevel} prob={noshow.probability ?? 0} />
            </div>
            
            {patient.chronic_conditions.length > 0 ? (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {patient.chronic_conditions.map((cond, i) => (
                  <span key={i} style={{
                    padding: '4px 10px', borderRadius: 99,
                    background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.3)',
                    color: '#A78BFA', fontSize: 11, fontWeight: 500,
                  }}>
                    {cond}
                  </span>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--t2)' }}>Aucune condition chronique connue.</div>
            )}
          </div>

          {/* Vitals & IoT */}
          <div style={{
            background: 'var(--s1)', borderRadius: 16, border: '1px solid var(--line)', padding: 20,
            boxShadow: anomaly.alert_critical ? '0 0 20px rgba(239, 68, 68, 0.15)' : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <IconActivity size={18} color={anomaly.alert_critical ? '#EF4444' : 'var(--t2)'} />
              <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: anomaly.alert_critical ? '#EF4444' : 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Biométrie IoT
              </div>
            </div>

            {anomaly.alert_critical && anomaly.narrative && (
              <div style={{
                marginBottom: 16, padding: '12px 14px', borderRadius: 10,
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
                color: '#EF4444', fontSize: 13, fontWeight: 500, lineHeight: 1.4,
              }}>
                <span style={{ fontWeight: 700, fontFamily: 'var(--f-mono)', fontSize: 10, display: 'block', marginBottom: 4, letterSpacing: '0.05em' }}>ALERTE CRITIQUE</span>
                {anomaly.narrative}
              </div>
            )}

            {vitals.samples_24h > 0 ? (
              <div style={{ display: 'flex', gap: 24 }}>
                {typeof vitals.hr === 'number' && (
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--t0)' }}>
                      {Math.round(vitals.hr)} <span style={{ fontSize: 12, color: 'var(--t3)', fontWeight: 400 }}>bpm</span>
                    </div>
                  </div>
                )}
                {typeof vitals.spo2 === 'number' && (
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--t0)' }}>
                      {Math.round(vitals.spo2)} <span style={{ fontSize: 12, color: 'var(--t3)', fontWeight: 400 }}>% SpO2</span>
                    </div>
                  </div>
                )}
                {typeof vitals.hrv === 'number' && (
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 600, color: 'var(--t0)' }}>
                      {Math.round(vitals.hrv)} <span style={{ fontSize: 12, color: 'var(--t3)', fontWeight: 400 }}>ms HRV</span>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--t2)' }}>Aucune donnée biométrique sur 24h.</div>
            )}
          </div>

        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          {/* Recent Symptoms Chat */}
          <div style={{
            background: 'var(--s1)', borderRadius: 16, border: '1px solid var(--line)', padding: 20,
            flex: 1,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <IconChat size={18} color="var(--t2)" />
              <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Derniers symptômes signalés
              </div>
            </div>

            {recent_symptoms.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {recent_symptoms.map((sym, i) => (
                  <div key={i} style={{
                    background: 'var(--s0)', border: '1px solid var(--line)', borderRadius: 10,
                    padding: '12px 14px', position: 'relative',
                  }}>
                    <div style={{ fontSize: 13, color: 'var(--t0)', lineHeight: 1.5, fontStyle: 'italic' }}>
                      &quot;{sym.content}&quot;
                    </div>
                    <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)', marginTop: 8, textAlign: 'right' }}>
                      {new Date(sym.created_at).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{
                padding: '24px 12px', textAlign: 'center',
                background: 'var(--s2)', borderRadius: 10, border: '1px dashed var(--line-strong)',
              }}>
                <div style={{ fontSize: 12.5, color: 'var(--t2)', fontWeight: 500 }}>
                  Aucun symptôme récent déclaré
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 3 }}>
                  pas de discussion dans les 7 derniers jours
                </div>
              </div>
            )}
          </div>
          
        </div>
      </div>
    </DashPage>
  );
}
