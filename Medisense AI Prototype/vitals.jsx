// Vitals / IoT dashboard

const { IconHeart, IconLung, IconWave, IconBluetooth, IconQR, IconSparkles, IconMore } = window;

const VITALS = [
  { key: 'hr', label: 'BPM', name: 'Fréquence cardiaque', value: 72, unit: '', color: '#F43F5E', icon: 'heart', trend: 'Normal · stable', trendDir: '↗' },
  { key: 'spo2', label: 'SpO₂', name: 'Saturation O₂', value: 98, unit: '%', color: '#38BDF8', icon: 'lung', trend: 'Excellent', trendDir: '✓' },
  { key: 'hrv', label: 'HRV', name: 'Variabilité', value: 42, unit: 'ms', color: '#A78BFA', icon: 'wave', trend: 'Bas · repos requis', trendDir: '↘' },
];

function CountUp({ to, dur = 1000 }) {
  const [n, setN] = React.useState(0);
  React.useEffect(() => {
    let raf, start; const from = 0;
    const tick = (t) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(Math.round(from + (to - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, dur]);
  return n;
}

function VitalCard({ v, active, onClick }) {
  const Icon = v.icon === 'heart' ? IconHeart : v.icon === 'lung' ? IconLung : IconWave;
  const display = v.key === 'spo2' ? <><CountUp to={v.value}/>{v.unit}</> : <><CountUp to={v.value}/>{v.unit && <span style={{fontSize:'0.6em',marginLeft:2,color:'var(--t2)'}}>{v.unit}</span>}</>;
  return (
    <div onClick={onClick} style={{
      flex: '0 0 auto', width: 168, padding: 16,
      background: 'var(--s1)', borderRadius: 18,
      border: active ? `1px solid ${v.color}55` : '1px solid var(--line)',
      cursor: 'pointer', position: 'relative', overflow: 'hidden',
      boxShadow: active ? `0 0 0 1px ${v.color}40, 0 12px 32px ${v.color}22` : 'none',
      transition: 'all .25s',
    }}>
      <div style={{
        position: 'absolute', top: -12, right: -12, width: 80, height: 80,
        borderRadius: '50%', background: `radial-gradient(circle, ${v.color}33, transparent 70%)`, filter: 'blur(8px)',
      }}/>
      <div style={{
        width: 32, height: 32, borderRadius: 10,
        background: `${v.color}22`, color: v.color,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 16, position: 'relative',
      }}><Icon size={18} stroke={1.8}/></div>
      <div style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 40,
        lineHeight: 1, color: v.color, letterSpacing: '-0.02em',
        textShadow: `0 0 20px ${v.color}55`,
      }}>{display}</div>
      <div style={{
        fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
        letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 6,
      }}>{v.label}</div>
      <div style={{
        fontFamily: 'var(--f-body)', fontSize: 11, color: 'var(--t1)', marginTop: 10,
        display: 'flex', alignItems: 'center', gap: 4,
      }}><span style={{ color: v.color }}>{v.trendDir}</span> {v.trend}</div>
    </div>
  );
}

function VitalsChart({ color }) {
  // generate a dummy waveform path
  const w = 320, h = 140;
  const pts = React.useMemo(() => {
    const arr = []; const n = 48;
    for (let i = 0; i < n; i++) {
      const x = (i / (n - 1)) * w;
      const baseline = h * 0.55;
      const y = baseline - (Math.sin(i * 0.55) * 22) - (Math.random() * 18 - 9);
      arr.push([x, y]);
    }
    return arr;
  }, [color]);
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  const areaPath = path + ` L ${w} ${h} L 0 ${h} Z`;
  const id = 'g_' + color.replace('#', '');
  return (
    <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
        <linearGradient id={id + 'l'} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={color} stopOpacity="0.9"/>
          <stop offset="100%" stopColor={color} stopOpacity="0.5"/>
        </linearGradient>
      </defs>
      {/* faint grid dashes */}
      {[0.25, 0.5, 0.75].map((p, i) => (
        <line key={i} x1="0" x2={w} y1={h * p} y2={h * p}
          stroke="rgba(148,163,184,0.08)" strokeDasharray="3 6" />
      ))}
      <path d={areaPath} fill={`url(#${id})`}/>
      <path d={path} fill="none" stroke={`url(#${id + 'l'})`} strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  );
}

function VitalsScreen() {
  const [active, setActive] = React.useState('hr');
  const [range, setRange] = React.useState('24h');
  const cur = VITALS.find(v => v.key === active);
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* header */}
      <div style={{ paddingTop: 60, padding: '60px 20px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
              letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
              whiteSpace: 'nowrap',
            }}>iot · sync il y a 12s</div>
            <h1 style={{
              fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
              margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
            }}>Signes vitaux</h1>
          </div>
          <button style={{
            width: 38, height: 38, borderRadius: 12,
            background: 'var(--s1)', border: '1px solid var(--line)',
            color: 'var(--t1)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}><IconMore size={18}/></button>
        </div>
      </div>

      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto' }}>
        {/* metric cards horizontal scroll */}
        <div className="scroll-hide" style={{
          display: 'flex', gap: 12, overflowX: 'auto', padding: '14px 20px',
        }}>
          {VITALS.map(v => <VitalCard key={v.key} v={v} active={v.key === active} onClick={() => setActive(v.key)}/>)}
        </div>

        {/* chart card */}
        <div style={{ padding: '8px 20px' }}>
          <div style={{
            background: 'var(--s1)', borderRadius: 20,
            border: '1px solid var(--line)', padding: 18,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
                  letterSpacing: '0.12em', textTransform: 'uppercase',
                }}>{cur.name}</div>
                <div style={{
                  fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
                  color: cur.color, marginTop: 4,
                }}>{cur.value}{cur.unit} <span style={{
                  fontSize: 11, color: 'var(--t2)', fontFamily: 'var(--f-body)', fontWeight: 400,
                  marginLeft: 4,
                }}>moy. {Math.round(cur.value * 0.94)}{cur.unit}</span></div>
              </div>
              <div style={{ display: 'flex', gap: 4 }}>
                {['1h','24h','7j'].map(r => (
                  <button key={r} onClick={() => setRange(r)} style={{
                    padding: '6px 11px', borderRadius: 99,
                    background: range === r ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
                    border: range === r ? 'none' : '1px solid var(--line)',
                    color: range === r ? '#fff' : 'var(--t1)',
                    fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
                    cursor: 'pointer', letterSpacing: '0.04em',
                  }}>{r}</button>
                ))}
              </div>
            </div>
            <div style={{ marginLeft: -8, marginRight: -8, marginTop: 14 }}>
              <VitalsChart color={cur.color}/>
            </div>
            {/* x-axis labels */}
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
              marginTop: 6, padding: '0 4px', letterSpacing: '0.04em',
            }}>
              <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>maint.</span>
            </div>
          </div>
        </div>

        {/* AI insight */}
        <div style={{ padding: '14px 20px 0' }}>
          <div style={{
            background: 'var(--s1)', borderRadius: 16,
            border: '1px solid var(--line)', padding: 14,
            display: 'flex', gap: 12,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 12,
              background: 'rgba(139,92,246,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#A78BFA', flexShrink: 0,
            }}><IconSparkles size={18} stroke={1.7}/></div>
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: '#A5B4FC',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
              }}>insight ia · xgboost</div>
              <div style={{
                fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t0)', lineHeight: 1.5,
              }}>Votre HRV diurne est en baisse de 18% sur 7 jours. Compatible avec un déficit de sommeil — visez 7h cette nuit.</div>
            </div>
          </div>
        </div>

        {/* device status */}
        <div style={{ padding: '14px 20px 110px' }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '12px 14px', borderRadius: 14,
            background: 'rgba(28,35,51,0.5)', border: '1px solid var(--line)',
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 10,
              background: 'rgba(56,189,248,0.15)', color: 'var(--oxy)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}><IconBluetooth size={16}/></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t0)', fontWeight: 500 }}>Mi Band 8 Pro</div>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
                letterSpacing: '0.06em', marginTop: 2,
              }}>connecté · batterie 84% · 4f8c…2a91</div>
            </div>
            <div style={{
              width: 8, height: 8, borderRadius: '50%', background: 'var(--safe)',
              boxShadow: '0 0 6px rgba(34,197,94,0.6)',
            }}/>
          </div>
        </div>
      </div>
    </div>
  );
}

// "No device" state — used in tweaks
function NoDeviceScreen() {
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 32px', textAlign: 'center' }}>
      <div style={{ position: 'relative', width: 140, height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24 }}>
        {[0,1,2].map(i => (
          <div key={i} style={{
            position: 'absolute', width: 60, height: 60, borderRadius: '50%',
            border: '1px solid rgba(56,189,248,0.4)',
            animation: `pulse-ring 2.4s ease-out ${i*0.8}s infinite`,
          }}/>
        ))}
        <div style={{
          width: 64, height: 64, borderRadius: 18,
          background: 'rgba(56,189,248,0.12)', color: 'var(--oxy)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><IconBluetooth size={28} stroke={1.5}/></div>
      </div>
      <h2 style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 24,
        margin: '0 0 8px', color: 'var(--t0)',
      }}>Connectez votre bracelet</h2>
      <p style={{
        fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t2)',
        margin: '0 0 28px', maxWidth: 280, lineHeight: 1.5,
      }}>Scannez le QR sur votre bracelet pour synchroniser fréquence cardiaque, SpO₂ et HRV.</p>
      <div style={{
        width: 120, height: 120, background: 'var(--s1)', borderRadius: 16,
        border: '1px solid var(--line)', padding: 16,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--t1)',
      }}><IconQR size={84} stroke={1.4}/></div>
    </div>
  );
}

Object.assign(window, { VitalsScreen, NoDeviceScreen });
