'use client';
import { use, useState, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { StatusBadge } from '@/components/status-badge';
import { ConfidenceBar } from '@/components/confidence-bar';
import { DashButton } from '@/components/dash-button';
import { DashPage } from '@/components/dashboard-shell';
import { IconBack, IconCheck, IconClose, IconAlert } from '@/components/icons';

type Severity = 'high' | 'med' | 'low' | 'mild' | 'moderate' | 'severe';
type VitalTone = 'normal' | 'warn' | 'critical';
type ActionKind = 'prescribe' | 'refer' | 'monitor' | 'alert';
type ActionState = 'pending' | 'approved' | 'rejected' | 'modified';

interface Symptom {
  name: string;
  severity: Severity;
  duration?: string;
  source?: string;
}

interface Vital {
  name: string;
  metric?: string;        // raw metric key (HR, SpO2, HRV…) — used to group sparkline points
  value: number | string;
  unit: string;
  status: VitalTone;
  statusLabel?: string;
  range?: string;
  ago?: string;
}

interface AIAction {
  id: string;
  type: string;
  kind?: ActionKind;
  title?: string;
  description: string;
  rationale?: string;
  confidence: number;
  status: ActionState;
  sourcePayload?: Record<string, unknown>;
}

interface DPAData {
  summary_id: string;
  patient: {
    uuid: string;
    name: string;
    age: number;
    dob: string;
    specialty?: string;
    sex?: string;
    chronicConditions: string[];
  };
  consultation: {
    uuid: string;
    timestamp: string;
    status: 'pending' | 'approved' | 'rejected';
    confidence: number;
    sources?: number;
    version?: number;
    freshnessMinutes?: number;
    reviewedAt?: string;
    doctorNote?: string;
  };
  symptoms: Symptom[];
  vitals: Vital[];
  iotTrend?: 'stable' | 'declining' | 'improving' | 'unknown' | string;
  actions: AIAction[];
  ragSummary?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function toStringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function toNumberValue(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function toOptionalNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function toSeverity(value: unknown): Severity {
  const normalized = String(value ?? '').toLowerCase();
  if (normalized === 'high' || normalized === 'med' || normalized === 'low' || normalized === 'mild' || normalized === 'moderate' || normalized === 'severe') {
    return normalized;
  }
  return 'moderate';
}

function toActionState(value: unknown): ActionState {
  const normalized = String(value ?? '').toLowerCase();
  if (normalized === 'approved' || normalized === 'rejected' || normalized === 'modified' || normalized === 'pending') {
    return normalized;
  }
  return 'pending';
}

function toConsultationStatus(value: unknown): 'pending' | 'approved' | 'rejected' {
  const normalized = String(value ?? '').toLowerCase();
  if (normalized === 'approved' || normalized === 'modified') return 'approved';
  if (normalized === 'rejected') return 'rejected';
  return 'pending';
}

function describeRecommendedAction(action: Record<string, unknown>): string {
  const kind = toStringValue(action.action).toLowerCase();
  if (kind === 'prescribe') {
    const medication = toStringValue(action.medication, 'Traitement');
    const dosage = toStringValue(action.dosage);
    return dosage ? `${medication} — ${dosage}` : medication;
  }
  if (kind === 'refer') {
    const specialist = toStringValue(action.specialist, 'spécialiste');
    const urgency = toStringValue(action.urgency, 'routine');
    return `Référer vers ${specialist} (${urgency})`;
  }
  if (kind === 'alert') {
    return toStringValue(action.message, 'Alerte clinique à traiter');
  }
  const metric = toStringValue(action.metric, 'paramètre clinique');
  const frequency = toStringValue(action.frequency, 'selon protocole');
  return `Surveiller ${metric} (${frequency})`;
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function normalizeDPAData(input: unknown, fallbackPatientUuid: string): DPAData {
  const raw = isRecord(input) ? input : {};
  const patient = isRecord(raw.patient) ? raw.patient : {};
  const consultation = isRecord(raw.consultation) ? raw.consultation : {};
  const iotSummary = isRecord(raw.iot_summary) ? raw.iot_summary : {};

  const summaryId = toStringValue(raw.summary_id, `${fallbackPatientUuid}-summary`);
  const patientUuid = toStringValue(patient.uuid, toStringValue(raw.patient_uuid, fallbackPatientUuid));
  const createdAt = toStringValue(raw.created_at, new Date().toISOString());
  const rawPatientName = toStringValue(patient.name, toStringValue(raw.patient_name));

  const symptomsRaw = Array.isArray(raw.symptoms) ? raw.symptoms : [];
  const symptoms: Symptom[] = symptomsRaw.map((entry) => {
    if (typeof entry === 'string') {
      return { name: entry, severity: 'moderate', source: 'chat' };
    }
    if (isRecord(entry)) {
      return {
        name: toStringValue(entry.name, 'Symptôme non spécifié'),
        severity: toSeverity(entry.severity),
        duration: toStringValue(entry.duration) || undefined,
        source: toStringValue(entry.source) || undefined,
      };
    }
    return { name: 'Symptôme non spécifié', severity: 'moderate' };
  });

  const vitalsFromUi = Array.isArray(raw.vitals) ? raw.vitals : [];
  const vitals: Vital[] = vitalsFromUi.length > 0
    ? vitalsFromUi
      .filter(isRecord)
      .map((v) => ({
        name: toStringValue(v.name, 'Mesure'),
        value: typeof v.value === 'string' || typeof v.value === 'number' ? v.value : '-',
        unit: toStringValue(v.unit),
        status: toStringValue(v.status) === 'critical' ? 'critical' : toStringValue(v.status) === 'warn' ? 'warn' : 'normal',
        statusLabel: toStringValue(v.statusLabel) || undefined,
        range: toStringValue(v.range) || undefined,
        ago: toStringValue(v.ago) || undefined,
      }))
    : (Array.isArray(iotSummary.latest_anomalies) ? iotSummary.latest_anomalies : [])
      .filter(isRecord)
      .map((a) => {
        const severity = toStringValue(a.severity).toLowerCase();
        const status: VitalTone = severity === 'critical' ? 'critical' : severity === 'moderate' || severity === 'mild' ? 'warn' : 'normal';
        const metricKey = toStringValue(a.metric, 'Mesure');
        return {
          name: metricKey,
          metric: metricKey,
          value: typeof a.value === 'number' ? a.value : toStringValue(a.value, '-'),
          unit: toStringValue(a.unit),
          status,
          statusLabel: toStringValue(a.severity) || undefined,
          range: typeof a.threshold === 'number' ? `seuil ${a.threshold}` : undefined,
          ago: toStringValue(a.detected_at) || undefined,
        };
      });

  const actionsFromAgent = Array.isArray(raw.agent_actions) ? raw.agent_actions : [];
  const actionsFromUi = Array.isArray(raw.actions) ? raw.actions : [];
  const actions: AIAction[] = actionsFromAgent.length > 0
    ? actionsFromAgent
      .filter(isRecord)
      .map((a, idx) => {
        const payload = isRecord(a.payload) ? a.payload : {};
        const modifiedPayload = isRecord(a.modified_payload) ? a.modified_payload : null;
        const effectivePayload = modifiedPayload ?? payload;
        const kindRaw = toStringValue(a.action_type, toStringValue(payload.action, 'monitor')).toLowerCase();
        const kind: ActionKind = ['prescribe', 'refer', 'monitor', 'alert'].includes(kindRaw)
          ? (kindRaw as ActionKind)
          : 'monitor';
        return {
          id: toStringValue(a.id, `${summaryId}-agent-action-${idx}`),
          type: kind,
          kind,
          title: toStringValue(effectivePayload.title) || undefined,
          description: describeRecommendedAction(effectivePayload),
          rationale: toStringValue(effectivePayload.reasoning) || undefined,
          confidence: toNumberValue(raw.confidence, 0.7),
          status: toActionState(a.status),
          sourcePayload: effectivePayload,
        };
      })
    : actionsFromUi.length > 0
      ? actionsFromUi
      .filter(isRecord)
      .map((a, idx) => {
        const type = toStringValue(a.type, toStringValue(a.kind, 'monitor'));
        return {
          id: toStringValue(a.id, `${summaryId}-action-${idx}`),
          type,
          kind: ['prescribe', 'refer', 'monitor', 'alert'].includes(toStringValue(a.kind))
            ? (toStringValue(a.kind) as ActionKind)
            : kindFromType(type),
          title: toStringValue(a.title) || undefined,
          description: toStringValue(a.description, 'Action IA suggérée'),
          rationale: toStringValue(a.rationale) || undefined,
          confidence: toNumberValue(a.confidence, toNumberValue(raw.confidence, 0.7)),
          status: toActionState(a.status),
          sourcePayload: isRecord(a.payload) ? a.payload : undefined,
        };
      })
      : (Array.isArray(raw.recommended_actions) ? raw.recommended_actions : [])
        .filter(isRecord)
        .map((a, idx) => {
          const kind = toStringValue(a.action, 'monitor').toLowerCase();
          const type = kind || 'monitor';
          return {
            id: `${summaryId}-action-${idx}`,
            type,
            kind: ['prescribe', 'refer', 'monitor', 'alert'].includes(type) ? (type as ActionKind) : 'monitor',
            title: undefined,
            description: describeRecommendedAction(a),
            rationale: toStringValue(a.reasoning) || undefined,
            confidence: toNumberValue(raw.confidence, 0.7),
            status: 'pending',
            sourcePayload: a,
          };
        });

  const chronicConditions = Array.isArray(patient.chronic_conditions)
    ? patient.chronic_conditions.filter((c): c is string => typeof c === 'string')
    : Array.isArray(raw.chronic_conditions)
      ? (raw.chronic_conditions as unknown[]).filter((c): c is string => typeof c === 'string')
      : [];

  const trendRaw = toStringValue(iotSummary.trend, 'unknown').toLowerCase();
  const iotTrend = ['stable', 'declining', 'improving'].includes(trendRaw)
    ? trendRaw
    : 'unknown';

  return {
    summary_id: summaryId,
    patient: {
      uuid: patientUuid,
      name: rawPatientName || `Patient ${patientUuid.slice(0, 8)}`,
      age: toNumberValue(patient.age, 0),
      dob: toStringValue(patient.dob, ''),
      specialty: toStringValue(patient.specialty) || undefined,
      sex: toStringValue(patient.sex) || undefined,
      chronicConditions,
    },
    consultation: {
      uuid: toStringValue(consultation.uuid, summaryId),
      timestamp: toStringValue(consultation.timestamp, createdAt),
      status: toConsultationStatus(consultation.status || raw.status),
      confidence: toNumberValue(consultation.confidence, toNumberValue(raw.confidence, 0)),
      sources: toOptionalNumber(consultation.sources),
      version: toNumberValue(raw.version, 1),
      freshnessMinutes: toNumberValue(raw.data_freshness_minutes, 0),
      reviewedAt: toStringValue(raw.reviewed_at) || undefined,
      doctorNote: toStringValue(raw.doctor_note) || undefined,
    },
    symptoms,
    vitals,
    iotTrend,
    actions,
    ragSummary: toStringValue(raw.ragSummary) || undefined,
  };
}

function pluralize(n: number, singular: string, plural?: string): string {
  return `${n} ${n <= 1 ? singular : plural ?? singular + 's'}`;
}

function formatFreshness(minutes: number): string {
  if (!minutes || minutes <= 0) return 'à l\u2019instant';
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `il y a ${hours}\u202fh`;
  const days = Math.floor(hours / 24);
  return `il y a ${days}\u202fj`;
}


function numericValue(value: Vital['value']): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string') {
    const parsed = Number(value.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

interface SparkSeries {
  metric: string | null;
  unit: string;
  values: number[];
}

/**
 * Build a per-metric sparkline series.
 *
 * `latest_anomalies` mixes HR (~70 bpm), SpO2 (~98 %), and HRV (~40 ms) in one
 * list. Plotting them together makes a meaningless zig-zag because the units
 * are incompatible. We group by metric and pick the one with the most points
 * — ties broken by the highest worst-case severity present.
 */
function buildSparkSeries(vitals: Vital[]): SparkSeries {
  const groups = new Map<string, { unit: string; points: { value: number; order: number; status: VitalTone }[] }>();
  vitals.forEach((v, idx) => {
    const val = numericValue(v.value);
    if (val === null) return;
    const key = v.metric ?? v.name;
    const order = v.ago ? Date.parse(v.ago) : Number.NaN;
    const bucket = groups.get(key) ?? { unit: v.unit, points: [] };
    bucket.points.push({
      value: val,
      order: Number.isFinite(order) ? order : idx,
      status: v.status,
    });
    groups.set(key, bucket);
  });

  if (groups.size === 0) return { metric: null, unit: '', values: [] };

  const severityWeight: Record<VitalTone, number> = { normal: 0, warn: 1, critical: 2 };
  let best: { key: string; unit: string; values: number[] } | null = null;
  groups.forEach((bucket, key) => {
    const sorted = [...bucket.points].sort((a, b) => a.order - b.order);
    const score = sorted.length * 10 + Math.max(...sorted.map((p) => severityWeight[p.status]));
    if (!best || score > best.values.length * 10) {
      best = { key, unit: bucket.unit, values: sorted.map((p) => p.value) };
    }
  });

  const winner = best!;
  return { metric: winner.key, unit: winner.unit, values: winner.values };
}

function sparklinePath(values: number[], width = 200, height = 40): string {
  if (values.length === 0) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  if (values.length === 1) {
    const y = height - ((values[0] - min) / range) * height;
    return `M 0 ${y} L ${width} ${y}`;
  }
  const span = values.length - 1;
  return values.map((v, i) => {
    const x = (width * i) / span;
    const y = height - ((v - min) / range) * height;
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');
}

const SEV_COLORS: Record<string, string> = {
  high: '#EF4444', severe: '#EF4444',
  med: '#F97316', moderate: '#F97316',
  low: '#22C55E', mild: '#22C55E',
};

const VITAL_TONES: Record<VitalTone, { c: string; bd: string }> = {
  critical: { c: '#EF4444', bd: 'rgba(239,68,68,0.45)' },
  warn:     { c: '#F97316', bd: 'rgba(249,115,22,0.45)' },
  normal:   { c: '#22C55E', bd: 'rgba(34,197,94,0.30)' },
};

const ACTION_KINDS: Record<ActionKind, { c: string; label: string; icon: string }> = {
  prescribe: { c: '#38BDF8', label: 'PRESCRIRE', icon: '℞' },
  refer:     { c: '#A78BFA', label: 'RÉFÉRER',   icon: '↗' },
  monitor:   { c: '#FBBF24', label: 'MONITORER', icon: '◔' },
  alert:     { c: '#EF4444', label: 'ALERTER',   icon: '⚠' },
};

function kindFromType(t: string): ActionKind {
  const s = t.toLowerCase();
  if (s.includes('prescri') || s.includes('medic')) return 'prescribe';
  if (s.includes('refer') || s.includes('réfé')) return 'refer';
  if (s.includes('monitor') || s.includes('surv')) return 'monitor';
  if (s.includes('alert') || s.includes('urgen')) return 'alert';
  return 'monitor';
}

function DpaCol({ tag, title, count, children }: { tag: string; title: string; count?: ReactNode; children: ReactNode }) {
  return (
    <div style={{
      background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 14,
      display: 'flex', flexDirection: 'column', minHeight: 0,
    }}>
      <div style={{
        padding: '14px 18px', borderBottom: '1px solid var(--line)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t4)', letterSpacing: '0.16em', textTransform: 'uppercase' }}>{tag}</div>
          <div style={{ fontFamily: 'var(--f-display)', fontSize: 15, fontWeight: 600, color: 'var(--t0)', marginTop: 2 }}>{title}</div>
        </div>
        {count !== undefined && (
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
            padding: '2px 8px', background: 'var(--s2)', borderRadius: 99,
            border: '1px solid var(--line)',
          }}>{count}</div>
        )}
      </div>
      <div className="scroll-hide" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10, overflowY: 'auto' }}>
        {children}
      </div>
    </div>
  );
}

function SymptomItem({ s }: { s: Symptom }) {
  const c = SEV_COLORS[s.severity] || '#A78BFA';
  return (
    <div style={{
      display: 'flex', gap: 10, padding: '11px 12px',
      background: 'var(--s2)', borderRadius: 10, border: '1px solid var(--line)',
    }}>
      <div style={{
        width: 6, alignSelf: 'stretch', borderRadius: 99,
        background: c, boxShadow: `0 0 6px ${c}80`, flexShrink: 0,
      }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12.5, color: 'var(--t0)', fontWeight: 500 }}>{s.name}</div>
        {(s.duration || s.source) && (
          <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 2 }}>
            {s.duration}{s.duration && s.source ? ' · ' : ''}{s.source}
          </div>
        )}
      </div>
    </div>
  );
}

function VitalItem({ v }: { v: Vital }) {
  const t = VITAL_TONES[v.status];
  const statusLabel = v.statusLabel ?? (v.status === 'critical' ? 'critique' : v.status === 'warn' ? 'modéré' : 'normal');
  return (
    <div style={{
      padding: '12px 14px', background: 'var(--s2)', borderRadius: 10,
      border: `1px solid ${t.bd}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <div style={{ fontSize: 12, color: 'var(--t2)' }}>{v.name}</div>
        <StatusBadge
          tone={v.status === 'critical' ? 'failed' : v.status === 'warn' ? 'pending' : 'sent'}
          label={statusLabel}
        />
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontFamily: 'var(--f-display)', fontSize: 26, fontWeight: 600, color: t.c, letterSpacing: '-0.02em' }}>
          {v.value}
        </span>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)' }}>{v.unit}</span>
      </div>
      {(v.range || v.ago) && (
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 4 }}>
          {v.range}{v.range && v.ago ? ' · ' : ''}{v.ago}
        </div>
      )}
    </div>
  );
}

function ActionCard({
  action,
  onApprove,
  onReject,
  onEdit,
}: {
  action: AIAction;
  onApprove: () => void;
  onReject: () => void;
  onEdit: (modified: string) => void;
}) {
  const kind = action.kind ?? kindFromType(action.type);
  const k = ACTION_KINDS[kind];
  const isApproved = action.status === 'approved';
  const isRejected = action.status === 'rejected';
  const [editMode, setEditMode] = useState(false);
  const [editValue, setEditValue] = useState(action.description);

  return (
    <div style={{
      background: isApproved ? 'rgba(34,197,94,0.06)' : isRejected ? 'rgba(239,68,68,0.05)' : 'var(--s2)',
      border: `1px solid ${isApproved ? 'rgba(34,197,94,0.30)' : isRejected ? 'rgba(239,68,68,0.30)' : 'var(--line)'}`,
      borderRadius: 12, padding: 14, opacity: isRejected ? 0.5 : 1,
      transition: 'all .25s',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '3px 9px', borderRadius: 99,
          fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
          color: k.c, background: `${k.c}1A`, border: `1px solid ${k.c}66`,
          letterSpacing: '0.08em',
        }}>
          <span>{k.icon}</span>{k.label}
        </span>
        <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t1)', fontWeight: 600 }}>
          {Math.round(action.confidence * 100)}%
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{ flex: 1, height: 4, background: 'var(--s3)', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{ width: `${action.confidence * 100}%`, height: '100%', background: 'var(--ai-grad)' }} />
        </div>
      </div>
      {action.title && (
        <div style={{
          fontSize: 13.5, color: 'var(--t0)', fontWeight: 600, marginBottom: 4, lineHeight: 1.3,
          textDecoration: isRejected ? 'line-through' : 'none',
        }}>
          {action.title}
        </div>
      )}
      {editMode ? (
        <textarea
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          style={{
            width: '100%', minHeight: 60, marginBottom: 8,
            background: 'var(--s3)', border: '1px solid var(--line-strong)', borderRadius: 6,
            color: 'var(--t0)', padding: 8, fontFamily: 'var(--f-body)', fontSize: 12.5,
            resize: 'vertical', outline: 'none', boxSizing: 'border-box',
          }}
        />
      ) : (
        <div style={{ fontSize: 12, color: 'var(--t1)', marginBottom: 8, lineHeight: 1.5 }}>
          {action.description}
        </div>
      )}
      {action.rationale && (
        <div style={{
          fontSize: 11.5, color: 'var(--t3)', fontStyle: 'italic', lineHeight: 1.5,
          marginBottom: 12, paddingLeft: 10, borderLeft: '2px solid var(--s3)',
        }}>
          {action.rationale}
        </div>
      )}
      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={onApprove} style={{
          flex: 1, padding: '7px 8px', borderRadius: 8, cursor: 'pointer',
          background: isApproved ? 'rgba(34,197,94,0.20)' : 'rgba(34,197,94,0.08)',
          border: `1px solid ${isApproved ? 'rgba(34,197,94,0.6)' : 'rgba(34,197,94,0.30)'}`,
          color: '#22C55E', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <IconCheck size={11} stroke={3} /> {isApproved ? 'Approuvé' : 'Approuver'}
        </button>
        <button onClick={onReject} style={{
          flex: 1, padding: '7px 8px', borderRadius: 8, cursor: 'pointer',
          background: isRejected ? 'rgba(239,68,68,0.18)' : 'rgba(239,68,68,0.06)',
          border: `1px solid ${isRejected ? 'rgba(239,68,68,0.6)' : 'rgba(239,68,68,0.25)'}`,
          color: '#EF4444', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <IconClose size={11} stroke={3} /> Rejeter
        </button>
        <button onClick={() => {
          if (editMode) onEdit(editValue);
          setEditMode((v) => !v);
        }} style={{
          padding: '7px 10px', borderRadius: 8, cursor: 'pointer',
          background: 'var(--s3)', border: '1px solid var(--line-strong)',
          color: 'var(--t1)', fontFamily: 'var(--f-body)', fontSize: 11.5, fontWeight: 500,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
        }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4z"/></svg>
          {editMode ? 'OK' : ''}
        </button>
      </div>
    </div>
  );
}

function PatientInfoBar({ patient, uuid, freshnessMinutes, version }: {
  patient: DPAData['patient'];
  uuid: string;
  freshnessMinutes: number;
  version: number;
}) {
  const sexLabel = patient.sex
    ? patient.sex.toUpperCase() === 'F' ? 'Femme' : patient.sex.toUpperCase() === 'M' ? 'Homme' : patient.sex
    : null;
  const meta: string[] = [];
  if (patient.age > 0) meta.push(`${patient.age} ans`);
  if (sexLabel) meta.push(sexLabel);
  if (patient.specialty) meta.push(patient.specialty);

  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 14,
      padding: '12px 16px',
      background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
      marginBottom: 12,
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: '50%',
        background: 'var(--ai-grad)', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600,
        color: '#fff', letterSpacing: '0.05em', flexShrink: 0,
      }}>
        {patient.name.split(' ').slice(0, 2).map((w) => w[0] ?? '').join('').toUpperCase() || '?'}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600, color: 'var(--t0)' }}>
          {patient.name}
        </div>
        <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)', letterSpacing: '0.04em' }}>
          ID {uuid.slice(0, 8)} · {meta.length > 0 ? meta.join(' · ') : 'profil incomplet'}
        </div>
      </div>
      {patient.chronicConditions.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
          {patient.chronicConditions.slice(0, 4).map((c) => (
            <span key={c} style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
              padding: '3px 8px', borderRadius: 99,
              color: '#F59E0B', background: 'rgba(245,158,11,0.10)',
              border: '1px solid rgba(245,158,11,0.30)',
              letterSpacing: '0.04em', textTransform: 'lowercase',
            }}>
              {c}
            </span>
          ))}
          {patient.chronicConditions.length > 4 && (
            <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>
              +{patient.chronicConditions.length - 4}
            </span>
          )}
        </div>
      )}
      <div style={{ flex: 1 }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)' }}>
        <span>v{version}</span>
        <span style={{ width: 1, height: 12, background: 'var(--line-strong)' }} />
        <span>généré {formatFreshness(freshnessMinutes)}</span>
      </div>
    </div>
  );
}

function TrendSparkline({ series }: { series: SparkSeries }) {
  const { metric, unit, values } = series;

  if (values.length < 2) {
    return (
      <div style={{
        padding: '10px 12px', background: 'var(--s2)', borderRadius: 10,
        border: '1px solid var(--line)',
      }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6,
        }}>
          {metric ? `Tendance · ${metric}` : 'Tendance biométrique'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--t2)' }}>
          {values.length === 0
            ? 'Aucune mesure exploitable pour la tendance.'
            : 'Donnée unique — au moins 2 points requis pour une tendance.'}
        </div>
      </div>
    );
  }

  const path = sparklinePath(values);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const delta = values[values.length - 1] - values[0];
  // Slope color: rising → amber, falling → red, flat → cyan.
  const color = Math.abs(delta) < 1e-9 ? '#38BDF8' : delta > 0 ? '#F59E0B' : '#EF4444';
  const direction = Math.abs(delta) < 1e-9 ? '→' : delta > 0 ? '↑' : '↓';

  return (
    <div style={{
      padding: '10px 12px', background: 'var(--s2)', borderRadius: 10,
      border: '1px solid var(--line)',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
        letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6,
      }}>
        <span>Tendance · {metric}</span>
        <span style={{ color }}>{direction} {Math.abs(delta).toFixed(1)}{unit}</span>
      </div>
      <svg width="100%" height="40" viewBox="0 0 200 40" preserveAspectRatio="none">
        <defs>
          <linearGradient id="dpa-spark" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity="0.5" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
        <path d={`${path} L 200 40 L 0 40 Z`} fill="url(#dpa-spark)" />
      </svg>
      <div style={{ fontSize: 11, color: 'var(--t2)', marginTop: 4 }}>
        {values.length} mesure{values.length > 1 ? 's' : ''} · min {min.toFixed(0)}{unit} · max {max.toFixed(0)}{unit}
      </div>
    </div>
  );
}

export default function DPAPage({ params }: { params: Promise<{ uuid: string }> }) {
  const { uuid } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const { data, isLoading, isError } = useQuery<DPAData>({
    queryKey: ['dpa-summary', uuid],
    queryFn: async () => {
      const { data } = await api.get(`/doctor/patient/${uuid}/dpa-summary`);
      return normalizeDPAData(data, uuid);
    },
  });

  const summaryId = data?.summary_id;

  const actionMutation = useMutation({
    mutationFn: async ({ actionId, status, payload }: { actionId: string; status: string; payload?: Record<string, unknown> }) => {
      if (!summaryId) throw new Error('summary_id missing');
      const { data } = await api.patch(`/doctor/dpa-summary/${summaryId}/action/${actionId}`, { status, ...payload });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dpa-summary', uuid] });
      showToast('Action mise à jour');
    },
    onError: (err) => {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        queryClient.invalidateQueries({ queryKey: ['dpa-summary', uuid] });
        showToast('Conflit — données rechargées');
      } else {
        showToast('Erreur lors de la mise à jour');
      }
    },
  });

  const validateMutation = useMutation({
    mutationFn: async () => {
      if (!summaryId) throw new Error('summary_id missing');
      const { data } = await api.post(`/doctor/dpa-summary/${summaryId}/approve`, { doctor_note: note });
      return data;
    },
    onSuccess: () => {
      showToast('DPA validé et signé');
      queryClient.invalidateQueries({ queryKey: ['dpa-summary', uuid] });
    },
    onError: () => showToast('Erreur lors de la validation'),
  });

  const rejectMutation = useMutation({
    mutationFn: async () => {
      if (!summaryId) throw new Error('summary_id missing');
      const { data } = await api.post(`/doctor/dpa-summary/${summaryId}/reject`, { doctor_note: rejectReason });
      return data;
    },
    onSuccess: () => {
      showToast('DPA rejeté');
      setShowRejectModal(false);
      setRejectReason('');
      queryClient.invalidateQueries({ queryKey: ['dpa-summary', uuid] });
    },
    onError: () => showToast('Erreur lors du rejet'),
  });

  if (isLoading) {
    return (
      <DashPage breadcrumb="agenda › chargement…" title="Résumé DPA">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
          <div style={{ display: 'flex', gap: 5 }}>
            {[0, 1, 2].map((i) => (
              <span key={i} style={{
                width: 8, height: 8, borderRadius: '50%', background: '#6366F1', display: 'inline-block',
                animation: `typing-dot 1.2s ease ${i * 0.15}s infinite`,
              }} />
            ))}
          </div>
        </div>
      </DashPage>
    );
  }

  if (isError || !data) {
    return (
      <DashPage breadcrumb="agenda › erreur" title="Résumé DPA"
        actions={
          <DashButton kind="ghost" small icon={<IconBack size={13} />} onClick={() => router.back()}>
            Retour à l&apos;agenda
          </DashButton>
        }
      >
        <div style={{ color: '#EF4444', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconAlert size={16} /> Impossible de charger les données du patient.
        </div>
      </DashPage>
    );
  }

  const statusTone = data.consultation.status === 'approved' ? 'approved' : data.consultation.status === 'rejected' ? 'rejected' : 'pending';
  const isPending = data.consultation.status === 'pending';
  const approvedCount = data.actions.filter((a) => a.status === 'approved').length;
  const sources = data.consultation.sources;
  const specialty = data.patient.specialty;
  const time = new Date(data.consultation.timestamp);
  const timeStr = `${time.getHours().toString().padStart(2, '0')}:${time.getMinutes().toString().padStart(2, '0')}`;
  const sparkSeries = buildSparkSeries(data.vitals);

  return (
    <>
      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 24, zIndex: 9999,
          background: 'var(--s2)', border: '1px solid var(--line-strong)',
          borderRadius: 10, padding: '10px 18px',
          color: 'var(--t0)', fontSize: 13, fontWeight: 500,
          animation: 'slide-down 0.2s ease',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}>
          {toast}
        </div>
      )}

      {/* Reject modal */}
      {showRejectModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9000,
          background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowRejectModal(false)}>
          <div
            style={{
              background: 'var(--s1)', border: '1px solid var(--line-strong)',
              borderRadius: 14, padding: 28, width: 420,
              animation: 'spring-in 0.35s ease',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontFamily: 'var(--f-display)', fontSize: 16, fontWeight: 600, color: 'var(--t0)', margin: '0 0 6px' }}>
              Motif de rejet
            </h3>
            <p style={{ fontSize: 12.5, color: 'var(--t2)', marginBottom: 16 }}>
              Expliquez la raison du rejet (requis pour l&apos;audit RGPD)
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Décrivez le motif de rejet…"
              style={{
                width: '100%', minHeight: 100,
                background: 'var(--s2)', border: '1px solid var(--line-strong)',
                borderRadius: 8, padding: '10px 12px', color: 'var(--t0)',
                fontFamily: 'var(--f-body)', fontSize: 13, resize: 'vertical', outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: rejectReason.length < 10 ? '#EF4444' : 'var(--t3)' }}>
                {rejectReason.length} car. (min. 10)
              </span>
              <div style={{ display: 'flex', gap: 8 }}>
                <DashButton kind="ghost" small onClick={() => setShowRejectModal(false)}>Annuler</DashButton>
                <DashButton
                  kind="solid"
                  small
                  disabled={rejectReason.length < 10}
                  loading={rejectMutation.isPending}
                  onClick={() => rejectMutation.mutate()}
                >
                  Confirmer le rejet
                </DashButton>
              </div>
            </div>
          </div>
        </div>
      )}

      <DashPage
        breadcrumb={`agenda › ${data.patient.name.toLowerCase()} · ${timeStr}`}
        title={`Résumé DPA — ${data.patient.name}`}
        subtitle={specialty ? specialty.charAt(0).toUpperCase() + specialty.slice(1) : undefined}
        actions={
          <>
            <DashButton kind="ghost" small icon={<IconBack size={13} />} onClick={() => router.back()}>
              Retour à l&apos;agenda
            </DashButton>
            <DashButton kind="solid" small onClick={() => setShowRejectModal(true)} disabled={!isPending}>
              Rejeter le résumé
            </DashButton>
            <DashButton
              kind="gradient"
              icon={<IconCheck size={13} stroke={2.5} />}
              loading={validateMutation.isPending}
              onClick={() => validateMutation.mutate()}
              disabled={!isPending}
            >
              Valider et signer
            </DashButton>
          </>
        }
      >
        <PatientInfoBar
          patient={data.patient}
          uuid={uuid}
          freshnessMinutes={data.consultation.freshnessMinutes ?? 0}
          version={data.consultation.version ?? 1}
        />

        {/* Status banner */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 18,
          padding: '14px 18px',
          background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
          marginBottom: 16, flexWrap: 'wrap',
        }}>
          <StatusBadge
            tone={statusTone}
            pulse={isPending}
            label={isPending ? `En attente · ${pluralize(approvedCount, 'action approuvée', 'actions approuvées')}` : undefined}
          />
          <ConfidenceBar value={data.consultation.confidence} label="Confiance globale" width={200} />
          <div style={{ flex: 1 }} />
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            fontFamily: 'var(--f-mono)', fontSize: 10.5, color: 'var(--t3)',
          }}>
            {typeof sources === 'number' && (
              <>
                <span>{pluralize(sources, 'source citée', 'sources citées')}</span>
                <span style={{ width: 1, height: 11, background: 'var(--line-strong)' }} />
              </>
            )}
            <span>{new Date(data.consultation.timestamp).toLocaleString('fr-FR', {
              day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
            })}</span>
          </div>
        </div>

        {/* 3 columns */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.2fr', gap: 14, minHeight: 480 }}>
          <DpaCol tag="clinique" title="Symptômes rapportés" count={data.symptoms.length}>
            {data.symptoms.length === 0 ? (
              <div style={{
                padding: '14px 12px', textAlign: 'center',
                background: 'var(--s2)', borderRadius: 10, border: '1px dashed var(--line-strong)',
              }}>
                <div style={{ fontSize: 12.5, color: 'var(--t2)', fontWeight: 500 }}>
                  Aucun nouveau symptôme déclaré
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 3 }}>
                  pas d&apos;interaction patient récente
                </div>
              </div>
            ) : (
              data.symptoms.map((s, i) => <SymptomItem key={i} s={s} />)
            )}
            {data.ragSummary && (
              <div style={{
                padding: '10px 12px', background: 'rgba(99,102,241,0.06)',
                borderRadius: 10, border: '1px solid rgba(99,102,241,0.30)',
                marginTop: 4,
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  fontFamily: 'var(--f-mono)', fontSize: 9.5, color: '#A78BFA',
                  letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
                }}>
                  <span>≋</span>Synthèse RAG
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--t1)', lineHeight: 1.5 }}>
                  {data.ragSummary}
                </div>
              </div>
            )}
          </DpaCol>

          <DpaCol
            tag="biométrie"
            title="Biométrie 24h"
            count={(() => {
              const n = data.vitals.filter((v) => v.status !== 'normal').length;
              return pluralize(n, 'anomalie');
            })()}
          >
            {data.vitals.length === 0 ? (
              <div style={{
                padding: '14px 12px', textAlign: 'center',
                background: 'var(--s2)', borderRadius: 10, border: '1px dashed var(--line-strong)',
              }}>
                <div style={{ fontSize: 12.5, color: 'var(--t2)', fontWeight: 500 }}>
                  Aucun capteur connecté
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 3 }}>
                  connectez un bracelet pour activer la biométrie
                </div>
              </div>
            ) : (
              <>
                {data.vitals.map((v, i) => <VitalItem key={i} v={v} />)}
                <TrendSparkline series={sparkSeries} />
              </>
            )}
          </DpaCol>

          <DpaCol tag="recommandations" title="Actions IA suggérées" count={pluralize(data.actions.length, 'action')}>
            {data.actions.length === 0 ? (
              <div style={{
                padding: '14px 12px', textAlign: 'center',
                background: 'var(--s2)', borderRadius: 10, border: '1px dashed var(--line-strong)',
              }}>
                <div style={{ fontSize: 12.5, color: 'var(--t2)', fontWeight: 500 }}>
                  Pas de recommandation IA
                </div>
                <div style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)', marginTop: 3 }}>
                  données cliniques insuffisantes — saisir manuellement
                </div>
              </div>
            ) : (
              data.actions.map((action) => (
                <ActionCard
                  key={action.id}
                  action={action}
                  onApprove={() => {
                    if (!isUuid(action.id)) {
                      showToast('Action locale non synchronisée');
                      return;
                    }
                    actionMutation.mutate({
                      actionId: action.id,
                      status: 'approved',
                    });
                  }}
                  onReject={() => {
                    if (!isUuid(action.id)) {
                      showToast('Action locale non synchronisée');
                      return;
                    }
                    actionMutation.mutate({ actionId: action.id, status: 'rejected' });
                  }}
                  onEdit={(modified) => {
                    if (!isUuid(action.id)) {
                      showToast('Action locale non synchronisée');
                      return;
                    }
                    actionMutation.mutate({
                      actionId: action.id,
                      status: 'modified',
                      payload: { modified_payload: { ...(action.sourcePayload ?? {}), description: modified } },
                    });
                  }}
                />
              ))
            )}
          </DpaCol>
        </div>

        {/* Doctor note */}
        <div style={{
          marginTop: 16,
          background: 'var(--s1)', border: '1px solid var(--line)', borderRadius: 12,
          padding: 14,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" strokeWidth="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 113 3L7 19l-4 1 1-4z"/></svg>
            <span style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
              letterSpacing: '0.14em', textTransform: 'uppercase',
            }}>
              Note du médecin (optionnel · audité)
            </span>
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Observations cliniques, contexte du patient, justification d&apos;une modification…"
            style={{
              width: '100%', minHeight: 60, resize: 'vertical',
              background: 'var(--s2)', border: '1px solid var(--line)', borderRadius: 8,
              color: 'var(--t0)', padding: 10,
              fontFamily: 'var(--f-body)', fontSize: 13, outline: 'none',
              boxSizing: 'border-box',
            }}
          />
        </div>
      </DashPage>
    </>
  );
}
