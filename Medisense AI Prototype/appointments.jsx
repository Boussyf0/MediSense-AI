// Appointments screen — risk-coded list

const { IconCalendar, IconChevron, IconMore } = window;

const RISK = {
  high: { color: '#EF4444', label: 'Risque élevé', dot: '#F43F5E' },
  med: { color: '#F97316', label: 'Risque modéré', dot: '#F97316' },
  low: { color: '#22C55E', label: 'Risque faible', dot: '#22C55E' },
};

const APPOINTMENTS = [
  { time: '09:30', name: 'Ahmed Benali', age: 58, doc: 'Dr. Merrouni · Cardiologie', risk: 'high', score: 67, reason: 'Suivi post-IDM · récidive douleur thoracique' },
  { time: '10:15', name: 'Fatima Zahra El Idrissi', age: 42, doc: 'Dr. Merrouni · Cardiologie', risk: 'med', score: 41, reason: 'HTA · ajustement Coversyl 5mg' },
  { time: '11:00', name: 'Youssef Tazi', age: 31, doc: 'Dr. Bennani · Médecine gén.', risk: 'low', score: 12, reason: 'Bilan annuel' },
  { time: '11:45', name: 'Khadija Amrani', age: 67, doc: 'Dr. Merrouni · Cardiologie', risk: 'high', score: 73, reason: 'Insuffisance cardiaque · dyspnée stade III' },
  { time: '14:00', name: 'Omar Chraibi', age: 52, doc: 'Dr. Bennani · Médecine gén.', risk: 'med', score: 38, reason: 'Diabète T2 · HbA1c 8.1%' },
  { time: '14:45', name: 'Salma Ouazzani', age: 28, doc: 'Dr. Bennani · Médecine gén.', risk: 'low', score: 8, reason: 'Renouvellement ordonnance' },
];

function ApptCard({ a, idx }) {
  const r = RISK[a.risk];
  return (
    <div style={{
      background: 'var(--s1)', borderRadius: 16,
      border: '1px solid var(--line)', padding: '14px 16px',
      display: 'flex', alignItems: 'flex-start', gap: 14,
      animation: `bubble-in .35s cubic-bezier(.34,1.36,.64,1) ${idx * 0.04}s both`,
    }}>
      {/* glowing dot */}
      <div style={{ paddingTop: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: r.dot,
          boxShadow: `0 0 10px 2px ${r.dot}80`,
          flexShrink: 0,
        }}/>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t1)', fontWeight: 600,
          letterSpacing: '0.04em', writingMode: 'horizontal-tb',
        }}>{a.time}</div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--f-display)', fontSize: 15, fontWeight: 600,
          color: 'var(--t0)', letterSpacing: '-0.005em',
        }}>{a.name} <span style={{
          fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t3)',
          fontWeight: 400, marginLeft: 4,
        }}>· {a.age}a</span></div>
        <div style={{
          fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)', marginTop: 2,
        }}>{a.doc}</div>
        <div style={{
          fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t1)', marginTop: 8,
          lineHeight: 1.4,
        }}>{a.reason}</div>
        <div style={{
          marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 10px', borderRadius: 99, whiteSpace: 'nowrap',
          background: `${r.color}1a`,
          border: `1px solid ${r.color}40`,
          animation: `spring-in .4s cubic-bezier(.34,1.36,.64,1) ${0.2 + idx*0.04}s both`,
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: r.color }}/>
          <span style={{
            fontFamily: 'var(--f-body)', fontSize: 11, fontWeight: 600,
            color: r.color, letterSpacing: '0.01em',
          }}>{r.label}</span>
          <span style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: r.color, opacity: 0.85,
          }}>· {a.score}%</span>
        </div>
      </div>
      <IconChevron size={16} color="var(--t3)" stroke={1.6}/>
    </div>
  );
}

function AppointmentsScreen() {
  const totals = APPOINTMENTS.reduce((acc, a) => { acc[a.risk]++; acc.total++; return acc; }, { high: 0, med: 0, low: 0, total: 0 });
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '60px 20px 8px' }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
        }}>vendredi 15 mai · cabinet</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <h1 style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
            margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
          }}>Agenda</h1>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)', letterSpacing: '0.04em',
          }}>{totals.total} pat.</div>
        </div>
      </div>

      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 110px' }}>
        {/* summary card with 3 sections */}
        <div style={{
          background: 'var(--s1)', borderRadius: 20,
          border: '1px solid var(--line)', padding: '16px 0',
          display: 'flex', marginBottom: 16,
        }}>
          {[
            { color: RISK.high.color, n: totals.high, label: 'Élevé' },
            { color: RISK.med.color, n: totals.med, label: 'Modéré' },
            { color: RISK.low.color, n: totals.low, label: 'Faible' },
          ].map((s, i, arr) => (
            <div key={i} style={{
              flex: 1, textAlign: 'center', padding: '0 8px',
              borderRight: i < arr.length - 1 ? '1px solid var(--line)' : 'none',
            }}>
              <div style={{
                fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 36,
                lineHeight: 1, color: s.color,
                textShadow: `0 0 18px ${s.color}55`,
                animation: `spring-in .6s cubic-bezier(.34,1.36,.64,1) ${i*0.08}s both`,
              }}>{s.n}</div>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 7,
              }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* timeline */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {APPOINTMENTS.map((a, i) => <ApptCard key={i} a={a} idx={i}/>)}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AppointmentsScreen });
