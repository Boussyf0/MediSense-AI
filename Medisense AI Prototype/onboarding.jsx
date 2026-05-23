// Splash + Onboarding + Login flow
// Exports: SplashScreen, OnboardingScreen, LoginScreen

const {
  IconWave, IconHeart, IconChat, IconShield, IconChevron,
  IconLock, IconSparkles, IconBack
} = window;

// ─────────────────────────────────────────────
// Animated waveform — 5 bars (used in splash + login)
// ─────────────────────────────────────────────
function Waveform({ size = 64, color = 'url(#aigrad)', bars = 5, animate = true }) {
  const w = size; const h = size * 0.95;
  const barW = w / (bars * 2 - 1);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id="aigrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6366F1"/>
          <stop offset="100%" stopColor="#8B5CF6"/>
        </linearGradient>
      </defs>
      {Array.from({ length: bars }).map((_, i) => {
        const x = i * barW * 2;
        return (
          <rect key={i}
            x={x} y={h/2 - h*0.1} width={barW} height={h*0.2} rx={barW/2}
            fill={color}
            style={{
              transformOrigin: `${x + barW/2}px ${h/2}px`,
              animation: animate ? `wave-bar 1.1s ease-in-out ${i * 0.13}s infinite` : 'none',
            }}
          />
        );
      })}
    </svg>
  );
}

// ─────────────────────────────────────────────
// Particle field background
// ─────────────────────────────────────────────
function ParticleField({ count = 28 }) {
  const dots = React.useMemo(() => Array.from({ length: count }).map((_, i) => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: 1 + Math.random() * 2,
    dx: -20 + Math.random() * 40,
    dy: -80 - Math.random() * 60,
    dur: 8 + Math.random() * 10,
    delay: Math.random() * 8,
  })), [count]);
  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
      {dots.map((d, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: `${d.x}%`, top: `${d.y}%`,
          width: d.size, height: d.size, borderRadius: '50%',
          background: 'rgba(167, 139, 250, 0.55)',
          boxShadow: '0 0 6px rgba(139,92,246,0.6)',
          '--dx': `${d.dx}px`, '--dy': `${d.dy}px`,
          animation: `drift ${d.dur}s ease-in ${d.delay}s infinite`,
        }} />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────
// SPLASH
// ─────────────────────────────────────────────
function SplashScreen({ onDone }) {
  React.useEffect(() => {
    const t = setTimeout(() => onDone && onDone(), 2600);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <div className="screen" style={{ background: '#0A0D14', alignItems: 'center', justifyContent: 'center' }}>
      <ParticleField count={20} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 28, paddingBottom: 60 }}>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {/* pulse rings */}
          {[0, 1].map(i => (
            <div key={i} style={{
              position: 'absolute', width: 160, height: 160, borderRadius: '50%',
              background: 'radial-gradient(circle, rgba(139,92,246,0.25), transparent 70%)',
              animation: `pulse-ring 2.4s ease-out ${i * 1.2}s infinite`,
            }} />
          ))}
          <div style={{
            width: 96, height: 96, borderRadius: 28,
            background: 'rgba(28,35,51,0.5)',
            border: '1px solid rgba(139,92,246,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            backdropFilter: 'blur(12px)',
            boxShadow: '0 8px 40px rgba(99,102,241,0.25)',
          }}>
            <Waveform size={56} />
          </div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 26,
            letterSpacing: '0.18em', color: '#F8FAFC', lineHeight: 1.2,
            display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: '0.32em',
          }}>MEDISENSE<span style={{
            background: 'var(--ai-grad)', WebkitBackgroundClip: 'text',
            backgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>AI</span></div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 9.5, color: '#64748B',
            letterSpacing: '0.16em', textTransform: 'uppercase', marginTop: 14,
            whiteSpace: 'nowrap',
          }}>Powered by RAG · XGBoost · LSTM</div>
        </div>
      </div>
      <div style={{
        position: 'absolute', bottom: 80, left: 0, right: 0,
        textAlign: 'center', fontFamily: 'var(--f-mono)', fontSize: 9, color: '#334155',
        letterSpacing: '0.14em',
      }}>v1.0.0 · build 4f8c2a · marrakech</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// ONBOARDING
// ─────────────────────────────────────────────
const ONBOARD_STEPS = [
  {
    icon: 'heart',
    title: 'Vos signes vitaux,\nen continu',
    desc: 'Synchronisez votre bracelet connecté pour suivre fréquence cardiaque, SpO₂ et HRV en temps réel.',
    tag: 'IoT · BLE',
  },
  {
    icon: 'chat',
    title: 'Une IA médicale\nen FR · AR · Darija',
    desc: 'Posez vos questions en langage naturel. Réponses sourcées avec score de confiance, jamais inventées.',
    tag: 'RAG · 30k corpus',
  },
  {
    icon: 'shield',
    title: 'Vos données,\nau Maroc',
    desc: 'Conforme RGPD et Loi 09-08. Hébergement local, modèle local, droit à l\'effacement en 1 tap.',
    tag: 'Loi 09-08',
  },
];

function OnboardCard({ step, idx }) {
  const Icon = step.icon === 'heart' ? IconHeart : step.icon === 'chat' ? IconChat : IconShield;
  return (
    <div style={{
      flex: '0 0 100%', display: 'flex', flexDirection: 'column',
      alignItems: 'center', textAlign: 'center', padding: '0 32px',
    }}>
      <div style={{
        width: 130, height: 130, borderRadius: 40,
        background: 'linear-gradient(160deg, rgba(99,102,241,0.18), rgba(139,92,246,0.06))',
        border: '1px solid rgba(139,92,246,0.25)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 36, position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', inset: -20,
          background: 'radial-gradient(circle at 30% 30%, rgba(99,102,241,0.4), transparent 60%)',
          filter: 'blur(20px)',
        }} />
        <div style={{ position: 'relative', color: '#C4B5FD' }}>
          <Icon size={56} stroke={1.4} />
        </div>
      </div>
      <div style={{
        fontFamily: 'var(--f-mono)', fontSize: 10, letterSpacing: '0.18em',
        color: 'var(--t3)', textTransform: 'uppercase', marginBottom: 14,
      }}>0{idx + 1} / 03 · {step.tag}</div>
      <h2 style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 30,
        lineHeight: 1.15, color: 'var(--t0)', margin: '0 0 18px',
        whiteSpace: 'pre-line', letterSpacing: '-0.02em',
      }}>{step.title}</h2>
      <p style={{
        fontFamily: 'var(--f-body)', fontSize: 15, lineHeight: 1.55,
        color: 'var(--t2)', margin: 0, maxWidth: 320,
      }}>{step.desc}</p>
    </div>
  );
}

function OnboardingScreen({ onDone }) {
  const [idx, setIdx] = React.useState(0);
  const next = () => idx < ONBOARD_STEPS.length - 1 ? setIdx(idx + 1) : onDone();
  return (
    <div className="screen" style={{ background: '#0A0D14' }}>
      <ParticleField count={18} />
      <div style={{ height: 54 }} />
      <div style={{
        display: 'flex', justifyContent: 'flex-end', padding: '8px 24px 0',
        position: 'relative', zIndex: 2,
      }}>
        <button onClick={onDone} style={{
          background: 'transparent', border: 'none', color: 'var(--t2)',
          fontFamily: 'var(--f-body)', fontSize: 14, cursor: 'pointer', padding: 8,
        }}>Passer</button>
      </div>
      <div style={{
        flex: 1, overflow: 'hidden', position: 'relative', zIndex: 2,
        display: 'flex', alignItems: 'center',
      }}>
        <div style={{
          display: 'flex', width: '100%',
          transform: `translateX(-${idx * 100}%)`,
          transition: 'transform .5s cubic-bezier(.65,.05,.36,1)',
        }}>
          {ONBOARD_STEPS.map((s, i) => <OnboardCard key={i} step={s} idx={i} />)}
        </div>
      </div>
      <div style={{ padding: '0 24px 56px', position: 'relative', zIndex: 2 }}>
        {/* progress pill */}
        <div style={{
          height: 4, background: 'rgba(148,163,184,0.10)', borderRadius: 99,
          overflow: 'hidden', marginBottom: 24,
        }}>
          <div style={{
            height: '100%', width: `${((idx + 1) / ONBOARD_STEPS.length) * 100}%`,
            background: 'var(--ai-grad)', borderRadius: 99,
            transition: 'width .4s ease',
          }} />
        </div>
        <button onClick={next} style={{
          width: '100%', height: 54, borderRadius: 16,
          background: 'var(--ai-grad)', border: 'none', color: '#fff',
          fontFamily: 'var(--f-body)', fontSize: 15, fontWeight: 600,
          cursor: 'pointer', letterSpacing: '0.01em',
          boxShadow: '0 8px 24px rgba(99,102,241,0.35)',
        }}>{idx < ONBOARD_STEPS.length - 1 ? 'Continuer' : 'Commencer'}</button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// LOGIN
// ─────────────────────────────────────────────
function LoginField({ label, type = 'text', value, onChange, error }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ marginBottom: 22 }}>
      <label style={{
        display: 'block', fontFamily: 'var(--f-mono)', fontSize: 10,
        color: error ? 'var(--pulse)' : 'var(--t3)',
        letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8,
        transition: 'color .2s',
      }}>{label}</label>
      <div style={{
        position: 'relative',
        animation: error ? 'shake .2s ease' : 'none',
      }}>
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          onFocus={() => setFocus(true)}
          onBlur={() => setFocus(false)}
          style={{
            width: '100%', height: 44,
            background: 'rgba(17, 24, 39, 0.6)',
            border: 'none', outline: 'none',
            borderBottom: '1px solid var(--s2)',
            color: 'var(--t0)',
            fontFamily: 'var(--f-body)', fontSize: 16,
            padding: '0 14px', borderRadius: '8px 8px 0 0',
            transition: 'background .2s',
          }}
        />
        {/* gradient bottom line on focus */}
        <div style={{
          position: 'absolute', left: 0, right: 0, bottom: 0, height: 2,
          background: error ? 'var(--pulse)' : 'var(--ai-grad)',
          borderRadius: 2,
          transform: focus || error ? 'scaleX(1)' : 'scaleX(0)',
          transformOrigin: 'left',
          transition: 'transform .25s',
          boxShadow: focus ? '0 0 12px rgba(139,92,246,0.4)' : 'none',
        }} />
      </div>
    </div>
  );
}

function LoginScreen({ onLogin, onBack }) {
  const [email, setEmail] = React.useState('ahmed.benali@medisense.ma');
  const [pw, setPw] = React.useState('');
  const [err, setErr] = React.useState(false);
  const [loading, setLoading] = React.useState(false);

  const submit = () => {
    if (!pw) {
      setErr(true);
      setTimeout(() => setErr(false), 600);
      return;
    }
    setLoading(true);
    setTimeout(() => onLogin(), 700);
  };
  return (
    <div className="screen" style={{ background: '#0A0D14' }}>
      <ParticleField count={12} />
      <div style={{ height: 60 }} />
      {onBack && (
        <button onClick={onBack} style={{
          position: 'absolute', top: 64, left: 16, zIndex: 5,
          background: 'transparent', border: 'none', color: 'var(--t2)',
          padding: 10, cursor: 'pointer', display: 'flex', alignItems: 'center',
        }}><IconBack size={22} /></button>
      )}
      <div style={{
        flex: 1, padding: '24px 32px', display: 'flex', flexDirection: 'column',
        position: 'relative', zIndex: 2,
      }}>
        <div style={{
          width: 52, height: 52, borderRadius: 16,
          background: 'rgba(28,35,51,0.6)',
          border: '1px solid rgba(139,92,246,0.25)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 28,
        }}>
          <Waveform size={32} />
        </div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 32,
          letterSpacing: '-0.02em', margin: '0 0 8px', color: 'var(--t0)',
        }}>Connexion</h1>
        <p style={{
          fontFamily: 'var(--f-body)', fontSize: 14, color: 'var(--t2)',
          margin: '0 0 36px', lineHeight: 1.5,
        }}>Bon retour. Vos données restent au Maroc.</p>

        <LoginField label="Email" value={email} onChange={setEmail} />
        <LoginField label="Mot de passe" type="password" value={pw} onChange={setPw} error={err} />

        <div style={{ textAlign: 'right', marginTop: -6, marginBottom: 28 }}>
          <a style={{
            fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
            textDecoration: 'none', cursor: 'pointer',
          }}>Mot de passe oublié ?</a>
        </div>

        <button onClick={submit} disabled={loading} style={{
          width: '100%', height: 54, borderRadius: 99,
          background: 'var(--ai-grad)', border: 'none', color: '#fff',
          fontFamily: 'var(--f-body)', fontSize: 15, fontWeight: 600,
          cursor: 'pointer',
          boxShadow: '0 8px 24px rgba(99,102,241,0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          opacity: loading ? 0.8 : 1,
        }}>
          {loading ? (
            <span style={{ display: 'flex', gap: 4 }}>
              {[0,1,2].map(i => <span key={i} style={{
                width: 6, height: 6, borderRadius: '50%', background: '#fff',
                animation: `typing-dot 1s ease ${i*0.15}s infinite`,
              }} />)}
            </span>
          ) : 'Se connecter'}
        </button>

        <div style={{
          textAlign: 'center', marginTop: 24,
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)',
          letterSpacing: '0.12em', textTransform: 'uppercase',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          whiteSpace: 'nowrap',
        }}>
          <IconLock size={11} stroke={2} />
          chiffré · loi 09-08
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Waveform, ParticleField, SplashScreen, OnboardingScreen, LoginScreen });
