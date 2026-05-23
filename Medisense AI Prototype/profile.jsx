// Profile screen — settings groups

const { IconChevron, IconShield, IconBell, IconLanguage, IconLock,
  IconHistory, IconStethoscope, IconTrash, IconLogout, IconPill, IconUser } = window;

function SettingRow({ icon: Icon, label, sub, danger, last, onClick }) {
  return (
    <button onClick={onClick} style={{
      width: '100%', display: 'flex', alignItems: 'center', gap: 14,
      padding: '12px 14px', background: 'transparent', border: 'none',
      borderBottom: last ? 'none' : '1px solid var(--line)',
      color: danger ? 'var(--pulse)' : 'var(--t0)',
      cursor: 'pointer', textAlign: 'left',
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 9,
        background: danger ? 'rgba(244,63,94,0.12)' : 'var(--s2)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: danger ? 'var(--pulse)' : 'var(--t1)',
        flexShrink: 0,
      }}><Icon size={16} stroke={1.7}/></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: 'var(--f-body)', fontSize: 14, fontWeight: 500 }}>{label}</div>
        {sub && <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
          marginTop: 2, letterSpacing: '0.04em',
        }}>{sub}</div>}
      </div>
      {!danger && <IconChevron size={14} color="var(--t3)" stroke={1.6}/>}
    </button>
  );
}

function SettingGroup({ title, children }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{
        fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
        letterSpacing: '0.16em', textTransform: 'uppercase',
        marginBottom: 8, padding: '0 16px',
      }}>{title}</div>
      <div style={{
        background: 'var(--s1)', borderRadius: 16,
        border: '1px solid var(--line)', overflow: 'hidden',
      }}>{children}</div>
    </div>
  );
}

function ProfileScreen() {
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto' }}>
        {/* gradient mesh header */}
        <div style={{
          position: 'relative', paddingTop: 60, paddingBottom: 24,
          overflow: 'hidden',
        }}>
          {/* mesh blobs */}
          <div style={{
            position: 'absolute', top: -40, left: -40, width: 240, height: 240,
            background: 'radial-gradient(circle, rgba(99,102,241,0.4), transparent 60%)',
            filter: 'blur(40px)',
          }}/>
          <div style={{
            position: 'absolute', top: 20, right: -60, width: 220, height: 220,
            background: 'radial-gradient(circle, rgba(139,92,246,0.4), transparent 60%)',
            filter: 'blur(40px)',
          }}/>
          <div style={{
            position: 'absolute', inset: 0, background: 'rgba(10,13,20,0.55)',
          }}/>

          <div style={{ position: 'relative', zIndex: 2, padding: '20px 20px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
            {/* avatar with gradient ring */}
            <div style={{
              width: 84, height: 84, borderRadius: '50%',
              background: 'var(--ai-grad)',
              padding: 3, marginBottom: 14,
              boxShadow: '0 8px 32px rgba(99,102,241,0.4)',
            }}>
              <div style={{
                width: '100%', height: '100%', borderRadius: '50%',
                background: 'var(--s0)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--f-display)', fontSize: 30, fontWeight: 600,
                color: 'var(--t0)',
              }}>A</div>
            </div>
            <h1 style={{
              fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
              margin: '0 0 6px', letterSpacing: '-0.01em', color: 'var(--t0)',
              lineHeight: 1.2, display: 'block', whiteSpace: 'nowrap',
            }}>Ahmed Benali</h1>
            <div style={{
              fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
              letterSpacing: '0.06em', marginBottom: 14, lineHeight: 1.4,
              whiteSpace: 'nowrap',
            }}>uid · 4f8c2a91 · marrakech</div>
            <div className="grad-border" style={{
              padding: '6px 14px', borderRadius: 99,
              background: 'rgba(28,35,51,0.6)', backdropFilter: 'blur(8px)',
              fontFamily: 'var(--f-body)', fontSize: 11, fontWeight: 600,
              color: 'var(--t0)', display: 'inline-flex', alignItems: 'center', gap: 6,
              whiteSpace: 'nowrap',
            }}><IconStethoscope size={12} stroke={2}/> Patient · suivi cardio</div>
          </div>
        </div>

        {/* quick stats */}
        <div style={{ padding: '0 20px 4px', display: 'flex', gap: 8, marginTop: 4 }}>
          {[
            { label: 'sessions', n: '128' },
            { label: 'jours actifs', n: '47' },
            { label: 'urgences', n: '02' },
          ].map((s, i) => (
            <div key={i} style={{
              flex: 1, padding: '12px 10px',
              background: 'var(--s1)', borderRadius: 12,
              border: '1px solid var(--line)', textAlign: 'center',
            }}>
              <div style={{
                fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
                color: 'var(--t0)', lineHeight: 1,
              }}>{s.n}</div>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t3)',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 6,
              }}>{s.label}</div>
            </div>
          ))}
        </div>

        <div style={{ padding: '20px 4px 110px' }}>
          <SettingGroup title="Médical">
            <SettingRow icon={IconStethoscope} label="Mon dossier patient" sub="3 antécédents · HTA · diabète T2"/>
            <SettingRow icon={IconPill} label="Mes traitements" sub="2 actifs · coversyl · metformine"/>
            <SettingRow icon={IconHistory} label="Historique consultations" sub="12 sessions · dernière 2 jours" last/>
          </SettingGroup>

          <SettingGroup title="Préférences">
            <SettingRow icon={IconLanguage} label="Langue" sub="français · darija · العربية"/>
            <SettingRow icon={IconBell} label="Notifications" sub="urgences · médicaments"/>
            <SettingRow icon={IconUser} label="Compte & sécurité" sub="biométrie activée" last/>
          </SettingGroup>

          <SettingGroup title="Confidentialité · Loi 09-08">
            <SettingRow icon={IconShield} label="Politique de données" sub="hébergement maroc · jamais partagé"/>
            <SettingRow icon={IconLock} label="Chiffrement & journaux" sub="aes-256 · audit log"/>
            <SettingRow icon={IconTrash} label="Effacer toutes mes données" sub="droit à l'effacement · rgpd art. 17" danger last/>
          </SettingGroup>

          <SettingGroup title="Compte">
            <SettingRow icon={IconLogout} label="Se déconnecter" danger last/>
          </SettingGroup>

          <div style={{
            textAlign: 'center', fontFamily: 'var(--f-mono)', fontSize: 9.5,
            color: 'var(--t4)', letterSpacing: '0.14em', marginTop: 8,
          }}>medisense ai · v1.0.0 · build 4f8c2a</div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ProfileScreen });
