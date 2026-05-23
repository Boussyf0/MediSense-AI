// Patient extras: Consent (RGPD), Conversations history, Reminders

const { IconShield, IconCheck, IconChevron, IconBell, IconPill,
  IconHistory, IconChat: _PIc, IconTrash, IconBack, IconClose } = window;

// ───────── CONSENT (RGPD onboarding step) ─────────
const CONSENT_ITEMS = [
  { key: 'data', title: 'Stockage de mes données médicales',
    desc: 'Vos symptômes, conversations et signes vitaux sont stockés au Maroc, chiffrés (AES-256).',
    required: true },
  { key: 'iot', title: 'Synchronisation bracelet connecté',
    desc: 'Fréquence cardiaque, SpO₂ et HRV. Vous pouvez révoquer à tout moment.',
    required: false },
  { key: 'ml', title: 'Amélioration du modèle IA',
    desc: 'Vos retours anonymisés aident à améliorer la qualité des réponses. Aucune donnée nominative.',
    required: false },
  { key: 'urgency', title: 'Alertes d\'urgence (SAMU 141)',
    desc: 'Si l\'IA détecte un risque vital, elle peut appeler le SAMU à votre place.',
    required: false },
];

function ConsentScreen({ onDone }) {
  const [accepted, setAccepted] = React.useState({ data: true, iot: true, ml: false, urgency: true });
  const allRequired = CONSENT_ITEMS.filter(i => i.required).every(i => accepted[i.key]);
  return (
    <div className="screen" style={{ background: 'var(--s0)' }}>
      <div style={{ padding: '60px 24px 16px' }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: 'rgba(34,197,94,0.12)', color: 'var(--safe)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 18,
        }}><IconShield size={22} stroke={1.7}/></div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 26,
          margin: '0 0 6px', letterSpacing: '-0.02em', color: 'var(--t0)',
        }}>Vos données, votre choix</h1>
        <p style={{
          fontFamily: 'var(--f-body)', fontSize: 13, color: 'var(--t2)',
          margin: 0, lineHeight: 1.5,
        }}>Conforme <strong style={{color:'var(--t1)'}}>Loi 09-08</strong> et <strong style={{color:'var(--t1)'}}>RGPD</strong>. Vous pouvez modifier ces choix à tout moment dans Profil → Confidentialité.</p>
      </div>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '8px 16px 0' }}>
        {CONSENT_ITEMS.map(item => (
          <div key={item.key} style={{
            background: 'var(--s1)', borderRadius: 14,
            border: `1px solid ${accepted[item.key] ? 'rgba(99,102,241,0.35)' : 'var(--line)'}`,
            padding: 14, marginBottom: 10,
            transition: 'border-color .2s',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <button
                onClick={() => !item.required && setAccepted(a => ({ ...a, [item.key]: !a[item.key] }))}
                disabled={item.required}
                style={{
                  width: 44, height: 26, borderRadius: 99,
                  background: accepted[item.key] ? 'var(--ai-grad)' : 'rgba(148,163,184,0.18)',
                  border: 'none', cursor: item.required ? 'not-allowed' : 'pointer',
                  flexShrink: 0, position: 'relative', padding: 0,
                  opacity: item.required ? 0.7 : 1,
                  transition: 'background .2s',
                }}>
                <span style={{
                  position: 'absolute', top: 3, left: accepted[item.key] ? 21 : 3,
                  width: 20, height: 20, borderRadius: '50%', background: '#fff',
                  transition: 'left .2s',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                }}/>
              </button>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{
                    fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: 600, color: 'var(--t0)',
                  }}>{item.title}</div>
                  {item.required && <span style={{
                    fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t3)',
                    letterSpacing: '0.12em', textTransform: 'uppercase',
                  }}>requis</span>}
                </div>
                <div style={{
                  fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
                  marginTop: 4, lineHeight: 1.4,
                }}>{item.desc}</div>
              </div>
            </div>
          </div>
        ))}
        <div style={{
          marginTop: 6, padding: 12, borderRadius: 12,
          background: 'rgba(28,35,51,0.5)', border: '1px solid var(--line)',
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
          letterSpacing: '0.04em', lineHeight: 1.5,
        }}>
          <span style={{ color: 'var(--safe)' }}>●</span> droit d'accès · rectification · effacement · portabilité<br/>
          <span style={{ color: 'var(--safe)' }}>●</span> hébergement maroc (datacenter casablanca-tier3)<br/>
          <span style={{ color: 'var(--safe)' }}>●</span> jamais de partage tiers · jamais d'usage commercial
        </div>
      </div>
      <div style={{ padding: '14px 24px 36px' }}>
        <button onClick={onDone} disabled={!allRequired} style={{
          width: '100%', height: 52, borderRadius: 99,
          background: allRequired ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
          border: 'none', color: '#fff',
          fontFamily: 'var(--f-body)', fontSize: 15, fontWeight: 600,
          cursor: allRequired ? 'pointer' : 'not-allowed',
          opacity: allRequired ? 1 : 0.5,
          boxShadow: allRequired ? '0 8px 24px rgba(99,102,241,0.35)' : 'none',
        }}>J'accepte et je continue</button>
      </div>
    </div>
  );
}

// ───────── CONVERSATIONS HISTORY ─────────
const CONVOS = [
  { id: 1, title: 'Douleur thoracique aiguë', preview: 'L\'IA a contacté le SAMU 141. Vous avez reçu un protocole d\'urgence aspirine 300mg.', date: 'Aujourd\'hui · 14:22', tag: 'urgence', urgent: true, sources: 5 },
  { id: 2, title: 'Effets secondaires Coversyl', preview: 'Toux sèche persistante : effet possible de l\'IEC. Discutez avec Dr. Merrouni d\'un changement.', date: 'Hier · 09:48', tag: 'traitement', sources: 3 },
  { id: 3, title: 'Mal de tête + nuque raide', preview: 'Probable céphalée de tension. Repos, hydratation. Si persiste >48h ou fièvre → consultation.', date: '08 mai · 18:15', tag: 'symptômes', sources: 4 },
  { id: 4, title: 'Tension à 14/9 ce matin', preview: 'Légèrement élevée. Tendance stable sur 7j. Pas d\'action immédiate, surveillance demain.', date: '06 mai · 07:30', tag: 'mesure', sources: 2 },
  { id: 5, title: 'Régime diabète type 2', preview: 'Plan alimentaire darija : pain complet, légumineuses, éviter pâtisseries marocaines au miel.', date: '03 mai · 20:02', tag: 'nutrition', sources: 6 },
  { id: 6, title: 'Vaccin grippe nécessaire ?', preview: 'Oui, recommandé pour profil HTA + 58 ans. Centre santé Gueliz proche, créneaux libres.', date: '28 avr · 11:40', tag: 'prévention', sources: 2 },
];

const TAG_COLORS = {
  'urgence': { c: '#F43F5E', bg: 'rgba(244,63,94,0.12)' },
  'traitement': { c: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },
  'symptômes': { c: '#38BDF8', bg: 'rgba(56,189,248,0.12)' },
  'mesure': { c: '#22C55E', bg: 'rgba(34,197,94,0.12)' },
  'nutrition': { c: '#F59E0B', bg: 'rgba(245,158,11,0.12)' },
  'prévention': { c: '#94A3B8', bg: 'rgba(148,163,184,0.12)' },
};

function HistoryScreen() {
  const [filter, setFilter] = React.useState('all');
  const filters = ['all', ...Object.keys(TAG_COLORS)];
  const list = filter === 'all' ? CONVOS : CONVOS.filter(c => c.tag === filter);
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '60px 20px 8px' }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
        }}>{CONVOS.length} conversations · 30j</div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
          margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
        }}>Historique</h1>
      </div>
      <div className="scroll-hide" style={{
        display: 'flex', gap: 6, padding: '14px 20px 6px', overflowX: 'auto',
      }}>
        {filters.map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: '6px 12px', borderRadius: 99,
            background: filter === f ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
            border: filter === f ? 'none' : '1px solid var(--line)',
            color: filter === f ? '#fff' : 'var(--t1)',
            fontFamily: 'var(--f-mono)', fontSize: 10, fontWeight: 600,
            letterSpacing: '0.06em', textTransform: 'uppercase',
            cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
          }}>{f === 'all' ? 'tout' : f}</button>
        ))}
      </div>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '8px 16px 110px' }}>
        {list.map((c, idx) => {
          const t = TAG_COLORS[c.tag];
          return (
            <div key={c.id} style={{
              background: 'var(--s1)', borderRadius: 14,
              border: `1px solid ${c.urgent ? 'rgba(244,63,94,0.35)' : 'var(--line)'}`,
              padding: 14, marginBottom: 8,
              animation: `bubble-in .3s cubic-bezier(.34,1.36,.64,1) ${idx*0.04}s both`,
              position: 'relative', overflow: 'hidden',
            }}>
              {c.urgent && <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
                background: 'var(--pulse)',
                boxShadow: '0 0 12px rgba(244,63,94,0.5)',
              }}/>}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{
                  padding: '3px 8px', borderRadius: 99,
                  background: t.bg, color: t.c,
                  fontFamily: 'var(--f-mono)', fontSize: 9, fontWeight: 600,
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                }}>{c.tag}</span>
                <span style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
                  letterSpacing: '0.04em', marginLeft: 'auto',
                }}>{c.date}</span>
              </div>
              <div style={{
                fontFamily: 'var(--f-display)', fontSize: 14, fontWeight: 600,
                color: 'var(--t0)', marginBottom: 4, letterSpacing: '-0.005em',
              }}>{c.title}</div>
              <div style={{
                fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
                lineHeight: 1.5,
              }}>{c.preview}</div>
              <div style={{
                marginTop: 10, display: 'flex', alignItems: 'center', gap: 12,
                fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
              }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#A5B4FC' }}/>
                  {c.sources} sources rag
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ───────── REMINDERS ─────────
const REMINDERS = [
  { time: '08:00', name: 'Coversyl 5mg', sub: 'IEC · 1 comprimé · à jeun', taken: true, type: 'pill' },
  { time: '12:30', name: 'Metformine 850mg', sub: 'Antidiabétique · pendant repas', taken: true, type: 'pill' },
  { time: '14:00', name: 'Mesure tension', sub: 'Brassard · noter dans l\'app', taken: false, type: 'measure' },
  { time: '20:00', name: 'Metformine 850mg', sub: 'Antidiabétique · pendant repas', taken: false, type: 'pill' },
  { time: '22:00', name: 'Aspirine 75mg', sub: 'Antiagrégant · au coucher', taken: false, type: 'pill' },
];

function RemindersScreen() {
  const [items, setItems] = React.useState(REMINDERS);
  const taken = items.filter(i => i.taken).length;
  const pct = Math.round((taken / items.length) * 100);
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '60px 20px 8px' }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4,
        }}>aujourd'hui · 5 rappels</div>
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 28,
          margin: 0, letterSpacing: '-0.02em', color: 'var(--t0)',
        }}>Mes rappels</h1>
      </div>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 110px' }}>
        {/* progress card */}
        <div style={{
          background: 'var(--s1)', borderRadius: 18,
          border: '1px solid var(--line)', padding: 18, marginBottom: 16,
          position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', top: -30, right: -30, width: 140, height: 140,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(34,197,94,0.25), transparent 70%)',
            filter: 'blur(20px)',
          }}/>
          <div style={{ position: 'relative' }}>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
              letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8,
            }}>observance</div>
            <div style={{
              fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 44,
              color: 'var(--safe)', lineHeight: 1, letterSpacing: '-0.02em',
              textShadow: '0 0 20px rgba(34,197,94,0.4)',
            }}>{pct}%</div>
            <div style={{
              fontFamily: 'var(--f-body)', fontSize: 12, color: 'var(--t2)',
              marginTop: 6,
            }}>{taken} / {items.length} rappels validés</div>
            <div style={{
              marginTop: 14, height: 6, borderRadius: 99,
              background: 'rgba(148,163,184,0.15)', overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', width: `${pct}%`,
                background: 'linear-gradient(90deg, var(--safe), #16A34A)',
                borderRadius: 99,
                transition: 'width .4s ease',
                boxShadow: '0 0 8px rgba(34,197,94,0.4)',
              }}/>
            </div>
          </div>
        </div>
        {/* timeline */}
        <div style={{ position: 'relative' }}>
          <div style={{
            position: 'absolute', left: 22, top: 8, bottom: 8, width: 2,
            background: 'linear-gradient(180deg, rgba(99,102,241,0.5), rgba(99,102,241,0.05))',
          }}/>
          {items.map((r, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 12,
              marginBottom: 10, position: 'relative',
            }}>
              <div style={{
                width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
                background: r.taken ? 'var(--safe)' : 'var(--s1)',
                border: r.taken ? 'none' : '2px solid var(--line-strong)',
                color: r.taken ? '#fff' : 'var(--t2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--f-mono)', fontSize: 9, fontWeight: 700,
                letterSpacing: '0.04em',
                boxShadow: r.taken ? '0 0 0 4px rgba(34,197,94,0.15)' : 'none',
                position: 'relative', zIndex: 1,
              }}>
                {r.taken ? <IconCheck size={18} stroke={2.4}/> : r.time}
              </div>
              <div style={{
                flex: 1, padding: '12px 14px', borderRadius: 12,
                background: 'var(--s1)',
                border: '1px solid var(--line)',
                opacity: r.taken ? 0.6 : 1,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div>
                    <div style={{
                      fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: 600,
                      color: 'var(--t0)',
                      textDecoration: r.taken ? 'line-through' : 'none',
                    }}>{r.name}</div>
                    <div style={{
                      fontFamily: 'var(--f-body)', fontSize: 11, color: 'var(--t2)', marginTop: 2,
                    }}>{r.sub}</div>
                  </div>
                  {r.taken ? (
                    <div style={{
                      fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--safe)',
                      letterSpacing: '0.1em', textTransform: 'uppercase',
                    }}>{r.time} · pris</div>
                  ) : (
                    <button onClick={() => setItems(arr => arr.map((x, j) => j===i ? {...x, taken: true} : x))} style={{
                      padding: '6px 12px', borderRadius: 99,
                      background: 'var(--ai-grad)', border: 'none', color: '#fff',
                      fontFamily: 'var(--f-body)', fontSize: 11, fontWeight: 600,
                      cursor: 'pointer',
                      boxShadow: '0 4px 12px rgba(99,102,241,0.3)',
                    }}>Valider</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ConsentScreen, HistoryScreen, RemindersScreen });
