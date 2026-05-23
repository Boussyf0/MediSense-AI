// Chat screen — soutenance centerpiece
// Streaming AI bubble, urgency banner, voice waveform, sources sheet

const {
  IconBack, IconMore, IconMic, IconSend, IconAlert, IconSparkles,
  IconClose, IconDoc, IconLink, IconCheck,
} = window;

// Mock conversation
const CHAT_INIT = [
  {
    id: 'ai1',
    role: 'ai', lang: 'FR', confidence: 0.91,
    sources: [
      { title: 'Dyspnée — symptômes & causes', src: 'sante.gov.ma', date: '2024' },
      { title: 'Guide IDM — Société Marocaine de Cardiologie', src: 'smc.ma', date: '2023' },
      { title: 'Référentiel SAMU urgences cardiaques', src: 'samu.ma', date: '2024' },
    ],
    text: "Bonjour Ahmed. Vous décrivez une douleur thoracique avec essoufflement depuis 30 minutes — c'est un signe à ne pas négliger. Avez-vous déjà eu ce type de douleur, ou des antécédents cardiaques ?",
    urgent: true,
  },
];

// Streaming text used for the demo
const STREAM_TEXT = "Compris. La douleur en barre qui irradie dans le bras gauche, associée à un essoufflement, peut évoquer un syndrome coronarien aigu. Étant donné votre profil (HTA traitée, 58 ans), j'ai contacté le SAMU. En attendant : asseyez-vous, desserrez vos vêtements, et croquez l'aspirine 300mg que je vous indique ci-dessous.";

function MetaPill({ children, color = 'rgba(28,35,51,0.85)', mono = true, onClick, glow }) {
  return (
    <span onClick={onClick} style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '4px 9px', borderRadius: 99,
      background: color, color: 'var(--t1)',
      fontFamily: mono ? 'var(--f-mono)' : 'var(--f-body)',
      fontSize: 10, fontWeight: 500, letterSpacing: '0.04em',
      border: '1px solid var(--line)',
      cursor: onClick ? 'pointer' : 'default',
      boxShadow: glow ? '0 0 12px rgba(139,92,246,0.25)' : 'none',
      whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        width: 36, height: 4, borderRadius: 99,
        background: 'rgba(148,163,184,0.18)', overflow: 'hidden', display: 'inline-block',
      }}>
        <span style={{
          display: 'block', height: '100%', width: `${pct}%`,
          background: 'var(--ai-grad)', borderRadius: 99,
        }} />
      </span>
      <span style={{ fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t1)' }}>{pct}%</span>
    </span>
  );
}

function UrgencyBanner({ onCall }) {
  return (
    <div style={{
      margin: '8px 16px 0',
      borderRadius: 14, overflow: 'hidden',
      background: 'linear-gradient(95deg, #F43F5E 0%, #DC2626 100%)',
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 14px',
      boxShadow: '0 8px 28px rgba(244,63,94,0.35)',
      animation: 'slide-down .4s cubic-bezier(.2,.8,.2,1)',
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 10,
        background: 'rgba(255,255,255,0.18)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        animation: 'scale-pulse 1.5s ease-in-out infinite',
      }}>
        <IconAlert size={20} stroke={2} color="#fff" />
      </div>
      <div style={{ flex: 1, color: '#fff' }}>
        <div style={{ fontFamily: 'var(--f-body)', fontWeight: 600, fontSize: 13 }}>
          Urgence détectée — appelez maintenant
        </div>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, opacity: 0.85,
          letterSpacing: '0.06em', marginTop: 2,
        }}>141 · SAMU MAROC</div>
      </div>
      <button onClick={onCall} style={{
        background: '#fff', color: '#DC2626', border: 'none',
        padding: '7px 14px', borderRadius: 99,
        fontFamily: 'var(--f-body)', fontSize: 12, fontWeight: 700,
        cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
      }}>Appeler 141</button>
    </div>
  );
}

function AIBubble({ msg, streaming }) {
  return (
    <div style={{ animation: 'bubble-in .25s cubic-bezier(.34,1.36,.64,1)' }}>
      <div style={{
        position: 'relative',
        background: 'var(--s1)',
        borderRadius: '4px 16px 16px 16px',
        padding: '12px 14px',
        marginRight: 56, marginLeft: 16,
        overflow: 'hidden',
      }}>
        {/* gradient left border */}
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: 3,
          background: 'var(--ai-grad)',
          overflow: 'hidden',
        }}>
          {streaming && (
            <div style={{
              position: 'absolute', left: 0, right: 0, height: '40%',
              background: 'linear-gradient(180deg, transparent, #fff, transparent)',
              animation: 'border-travel 1.4s ease-in-out infinite',
            }} />
          )}
        </div>
        <div style={{
          fontFamily: 'var(--f-body)', fontSize: 14, lineHeight: 1.55,
          color: 'var(--t0)',
        }}>
          {msg.text}
          {streaming && (
            <span style={{
              display: 'inline-block', width: 8, height: 16,
              background: 'var(--ai-to)',
              marginLeft: 2, verticalAlign: '-2px',
              animation: 'streaming-cursor 1s steps(1) infinite',
            }} />
          )}
        </div>
      </div>
      {/* meta row */}
      {!streaming && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap',
          marginLeft: 20, marginTop: 8, marginRight: 16,
        }}>
          <MetaPill>{msg.lang}</MetaPill>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '4px 9px', borderRadius: 99,
            background: 'rgba(28,35,51,0.85)',
            border: '1px solid var(--line)',
          }}><ConfidenceBar value={msg.confidence}/></span>
          {msg.sources && (
            <MetaPill onClick={msg.onSourcesClick} glow>
              <IconLink size={10} stroke={2}/> rag · {msg.sources.length} sources
            </MetaPill>
          )}
        </div>
      )}
    </div>
  );
}

function UserBubble({ text }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 16px',
      animation: 'bubble-in .2s cubic-bezier(.34,1.36,.64,1)' }}>
      <div style={{
        maxWidth: '78%',
        background: 'var(--ai-grad)',
        borderRadius: '20px 4px 20px 20px',
        padding: '10px 14px',
        color: '#fff',
        fontFamily: 'var(--f-body)', fontSize: 14, lineHeight: 1.5,
        boxShadow: '0 6px 20px rgba(99,102,241,0.3)',
      }}>{text}</div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div style={{
      background: 'var(--s1)',
      borderRadius: '4px 16px 16px 16px',
      padding: '14px 16px',
      marginRight: 200, marginLeft: 16,
      display: 'flex', alignItems: 'center', gap: 5,
      borderLeft: '3px solid transparent',
      borderImage: 'linear-gradient(180deg, #6366F1, #8B5CF6) 1',
      width: 'fit-content',
    }}>
      {[0,1,2].map(i => <span key={i} style={{
        width: 5, height: 5, borderRadius: '50%',
        background: 'var(--ai-to)',
        animation: `typing-dot 1.2s ease ${i*0.15}s infinite`,
      }}/>)}
    </div>
  );
}

// Voice recording bars (animated, pseudo-amplitude)
function VoiceBars() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, height: 22 }}>
      {[0,1,2,3,4].map(i => (
        <div key={i} style={{
          width: 3, borderRadius: 2,
          background: 'var(--ai-grad)',
          height: '100%',
          transformOrigin: 'center',
          animation: `wave-bar 0.${5+i}s ease-in-out ${i*0.07}s infinite`,
        }}/>
      ))}
    </div>
  );
}

// Suggestion chip with gradient border
function ChipSuggest({ label, onClick }) {
  return (
    <button onClick={onClick} className="grad-border" style={{
      padding: '9px 14px', borderRadius: 99,
      background: 'rgba(17,24,39,0.7)',
      border: 'none', color: 'var(--t0)',
      fontFamily: 'var(--f-body)', fontSize: 12.5, fontWeight: 500,
      cursor: 'pointer', whiteSpace: 'nowrap',
    }}>{label}</button>
  );
}

// Empty state — first open
function ChatEmpty({ onSuggest }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '0 24px', textAlign: 'center',
    }}>
      <div style={{
        width: 96, height: 96, borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(139,92,246,0.4), rgba(99,102,241,0.1) 70%, transparent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 20, animation: 'empty-pulse 2.4s ease-in-out infinite',
      }}>
        <div style={{ color: '#C4B5FD' }}><IconSparkles size={32} stroke={1.5}/></div>
      </div>
      <h2 style={{
        fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 26,
        margin: '0 0 8px', color: 'var(--t0)', letterSpacing: '-0.01em',
      }}>Bonjour Ahmed <span style={{ display: 'inline-block', animation: 'wave-bar 2s ease-in-out infinite' }}>👋</span></h2>
      <p style={{
        fontFamily: 'var(--f-body)', fontSize: 14, color: 'var(--t2)',
        margin: '0 0 28px', lineHeight: 1.5, maxWidth: 280,
      }}>Décrivez vos symptômes ou posez une question médicale. Je réponds en FR, AR ou darija.</p>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
        <ChipSuggest label="Mes symptômes" onClick={() => onSuggest('Je sens une douleur dans la poitrine depuis 30 minutes, et j\'ai du mal à respirer.')}/>
        <ChipSuggest label="Mon traitement" onClick={() => onSuggest('Quels effets secondaires pour le Coversyl 5mg ?')}/>
        <ChipSuggest label="Urgence" onClick={() => onSuggest('Mon père a une douleur thoracique aiguë, que faire ?')}/>
      </div>
    </div>
  );
}

// Sources bottom sheet
function SourcesSheet({ sources, onClose }) {
  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 50,
      background: 'rgba(0,0,0,0.55)',
      animation: 'fadeIn .2s', display: 'flex', alignItems: 'flex-end',
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', background: 'var(--s1)',
        borderRadius: '20px 20px 0 0',
        padding: '20px 20px 32px',
        animation: 'slide-up .3s cubic-bezier(.2,.8,.2,1)',
        borderTop: '1px solid var(--line-strong)',
      }}>
        <div style={{
          width: 40, height: 4, borderRadius: 99, background: 'var(--s3)',
          margin: '0 auto 18px',
        }}/>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <div style={{ color: '#A5B4FC' }}><IconDoc size={18} stroke={1.6}/></div>
          <h3 style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 17,
            color: 'var(--t0)', margin: 0,
          }}>Sources citées · RAG</h3>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sources.map((s, i) => (
            <div key={i} style={{
              padding: '12px 14px', borderRadius: 12,
              background: 'var(--s2)', border: '1px solid var(--line)',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: 'rgba(99,102,241,0.18)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--f-mono)', fontSize: 11, fontWeight: 700,
                color: '#A5B4FC',
              }}>0{i+1}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontFamily: 'var(--f-body)', fontSize: 13, fontWeight: 500,
                  color: 'var(--t0)', overflow: 'hidden', textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>{s.title}</div>
                <div style={{
                  fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
                  marginTop: 3, letterSpacing: '0.02em',
                }}>{s.src} · {s.date}</div>
              </div>
              <IconLink size={14} color="var(--t3)" stroke={1.7}/>
            </div>
          ))}
        </div>
      </div>
      <style>{`
        @keyframes fadeIn { from{opacity:0} to{opacity:1} }
        @keyframes slide-up { from{transform:translateY(100%)} to{transform:translateY(0)} }
      `}</style>
    </div>
  );
}

function ChatScreen({ initialUrgent = true, initialEmpty = false }) {
  const [empty, setEmpty] = React.useState(initialEmpty);
  const [messages, setMessages] = React.useState(initialEmpty ? [] : CHAT_INIT);
  const [urgent, setUrgent] = React.useState(initialUrgent);
  const [input, setInput] = React.useState('');
  const [recording, setRecording] = React.useState(false);
  const [showSources, setShowSources] = React.useState(null);
  const [streamingMsg, setStreamingMsg] = React.useState(null);
  const [typing, setTyping] = React.useState(false);
  const scrollRef = React.useRef();

  const scrollDown = () => {
    requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    });
  };

  React.useEffect(scrollDown, [messages, streamingMsg, typing]);

  const send = (text) => {
    if (!text.trim()) return;
    setEmpty(false);
    const userMsg = { id: 'u' + Date.now(), role: 'user', text };
    setMessages(m => [...m, userMsg]);
    setInput('');

    // simulate AI response
    setTyping(true);
    setTimeout(() => {
      setTyping(false);
      const targetText = STREAM_TEXT;
      let i = 0;
      setStreamingMsg({ text: '', role: 'ai' });
      const tick = () => {
        i += Math.max(1, Math.floor(Math.random() * 4));
        if (i >= targetText.length) {
          setStreamingMsg(null);
          setMessages(m => [...m, {
            id: 'a' + Date.now(), role: 'ai',
            text: targetText, lang: 'FR', confidence: 0.87,
            sources: [
              { title: 'Aspirine — protocole urgence cardiaque', src: 'medicament.ma', date: '2025' },
              { title: 'Syndrome coronarien aigu — guide SMC', src: 'smc.ma', date: '2024' },
            ],
          }]);
          if (text.toLowerCase().includes('thoracique') || text.toLowerCase().includes('poitrine')) setUrgent(true);
          return;
        }
        setStreamingMsg({ text: targetText.slice(0, i), role: 'ai' });
        scrollDown();
        setTimeout(tick, 26);
      };
      tick();
    }, 700);
  };

  const sourcesForCurrent = showSources;

  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', background: 'var(--s0)', overflow: 'hidden' }}>
      {/* header */}
      <div style={{
        paddingTop: 54, paddingBottom: 12, paddingLeft: 8, paddingRight: 12,
        display: 'flex', alignItems: 'center', gap: 4,
        background: 'rgba(10,13,20,0.85)', backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--line)', zIndex: 5,
      }}>
        <button style={{
          width: 40, height: 40, background: 'transparent', border: 'none',
          color: 'var(--t1)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><IconBack size={22}/></button>
        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 16,
            color: 'var(--t0)', letterSpacing: '-0.01em',
          }}>Assistant IA</div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
            display: 'flex', alignItems: 'center', gap: 5, marginTop: 1,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%', background: 'var(--safe)',
              boxShadow: '0 0 6px rgba(34,197,94,0.6)',
            }}/>
            en ligne · mistral-7B
          </div>
        </div>
        <button style={{
          width: 40, height: 40, background: 'transparent', border: 'none',
          color: 'var(--t1)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><IconMore size={20}/></button>
      </div>

      {urgent && !empty && <UrgencyBanner onCall={() => setUrgent(false)} />}

      <div ref={scrollRef} className="scroll-hide" style={{
        flex: 1, overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: 14,
        padding: '14px 0 8px',
      }}>
        {empty ? (
          <ChatEmpty onSuggest={(t) => send(t)} />
        ) : (
          <>
            {messages.map(m => m.role === 'ai' ? (
              <AIBubble key={m.id} msg={{ ...m, onSourcesClick: () => setShowSources(m.sources) }} />
            ) : (
              <UserBubble key={m.id} text={m.text} />
            ))}
            {typing && <TypingBubble/>}
            {streamingMsg && <AIBubble msg={{ ...streamingMsg, lang: 'FR', confidence: 0 }} streaming />}
          </>
        )}
        <div style={{ height: 4 }}/>
      </div>

      {/* input */}
      <div style={{
        padding: '10px 12px 92px',
        borderTop: '1px solid var(--line)',
        background: 'rgba(10,13,20,0.92)', backdropFilter: 'blur(12px)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--s1)', borderRadius: 24,
          border: '1px solid var(--line)',
          padding: 4, paddingLeft: 14,
        }}>
          {recording ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0' }}>
              <VoiceBars />
              <span style={{
                fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t2)',
                letterSpacing: '0.04em',
              }}>écoute · 00:0{Math.floor(Date.now()/1000)%10}</span>
            </div>
          ) : (
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send(input)}
              placeholder="Décrivez vos symptômes…"
              style={{
                flex: 1, height: 40, background: 'transparent',
                border: 'none', outline: 'none', color: 'var(--t0)',
                fontFamily: 'var(--f-body)', fontSize: 14,
              }}
            />
          )}
          <button onClick={() => setRecording(r => !r)} style={{
            width: 40, height: 40, borderRadius: 99,
            border: 'none', cursor: 'pointer',
            background: recording ? 'var(--ai-grad)' : 'transparent',
            color: recording ? '#fff' : 'var(--t2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: recording ? '0 0 16px rgba(139,92,246,0.5)' : 'none',
          }}><IconMic size={18}/></button>
          <button onClick={() => send(input)} disabled={!input.trim() && !recording} style={{
            width: 40, height: 40, borderRadius: 99,
            border: 'none', cursor: 'pointer',
            background: (input.trim() || recording) ? 'var(--ai-grad)' : 'rgba(28,35,51,0.6)',
            color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: (input.trim() || recording) ? 1 : 0.5,
            transition: 'all .2s',
          }}><IconSend size={16}/></button>
        </div>
      </div>

      {showSources && <SourcesSheet sources={showSources} onClose={() => setShowSources(null)}/>}
    </div>
  );
}

Object.assign(window, { ChatScreen });
