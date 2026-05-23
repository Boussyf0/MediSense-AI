// Top-level App — Design Canvas with all 4 roles + patient mobile prototype

const {
  DesignCanvas, DCSection, DCArtboard, DCPostIt,
  IOSDevice,
  TweaksPanel, useTweaks, TweakSection, TweakRadio, TweakToggle, TweakButton,
  IconChat, IconHeart, IconCalendar, IconUser, IconShield, IconHistory, IconBell,
  SplashScreen, OnboardingScreen, LoginScreen,
  ChatScreen, VitalsScreen, NoDeviceScreen, AppointmentsScreen, ProfileScreen,
  ConsentScreen, HistoryScreen, RemindersScreen,
  DoctorLogin, DoctorAgenda, DoctorDpa,
  SecretaryAgenda, SecretaryCrm,
  AdminAudit, AdminUsers, AdminRerank,
} = window;

// Mini phone wrapper to embed inside artboards (skips heavy IOSDevice frame)
function PhoneFrame({ children, label }) {
  return (
    <div style={{
      width: 320, height: 680, borderRadius: 38,
      background: '#0A0D14',
      border: '8px solid #1a1f2e',
      boxShadow: '0 30px 80px rgba(0,0,0,0.4), inset 0 0 0 1px rgba(255,255,255,0.05)',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* status bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 44, zIndex: 100,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 22px',
        fontFamily: 'var(--f-body)', fontSize: 12, fontWeight: 600, color: '#fff',
        pointerEvents: 'none',
      }}>
        <span>9:41</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <svg width="14" height="9" viewBox="0 0 14 9" fill="none"><path d="M1 7h2v1H1zM4 5h2v3H4zM7 3h2v5H7zM10 1h2v7h-2z" fill="#fff"/></svg>
          <svg width="20" height="10" viewBox="0 0 20 10" fill="none"><rect x="1" y="1" width="16" height="8" rx="2" stroke="#fff" opacity="0.6"/><rect x="3" y="3" width="11" height="4" rx="1" fill="#fff"/><rect x="18" y="4" width="1.5" height="2" fill="#fff" opacity="0.6"/></svg>
        </span>
      </div>
      {/* dynamic island */}
      <div style={{
        position: 'absolute', top: 11, left: '50%', transform: 'translateX(-50%)',
        width: 100, height: 28, borderRadius: 99, background: '#000', zIndex: 101,
      }}/>
      {/* content */}
      <div style={{ position: 'absolute', inset: 0 }}>{children}</div>
      {/* home indicator */}
      <div style={{
        position: 'absolute', bottom: 8, left: '50%', transform: 'translateX(-50%)',
        width: 120, height: 4, borderRadius: 99, background: 'rgba(255,255,255,0.45)', zIndex: 100,
      }}/>
    </div>
  );
}

// Browser chrome wrapper for desktop dashboards
function BrowserFrame({ url, role, children, w = 1280, h = 800 }) {
  return (
    <div style={{
      width: w, height: h, borderRadius: 12,
      background: '#0a0d14',
      boxShadow: '0 30px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)',
      overflow: 'hidden', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        height: 36, background: '#1a1f2e', display: 'flex', alignItems: 'center',
        padding: '0 14px', gap: 8, borderBottom: '1px solid rgba(255,255,255,0.05)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {['#FF5F56','#FFBD2E','#27C93F'].map(c => (
            <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }}/>
          ))}
        </div>
        <div style={{
          flex: 1, height: 22, marginLeft: 12, marginRight: 12,
          background: '#0a0d14', borderRadius: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--f-mono)', fontSize: 10, color: '#94A3B8',
          letterSpacing: '0.04em',
          border: '1px solid rgba(255,255,255,0.05)', padding: '0 12px',
        }}>
          <span style={{ color: '#22C55E', marginRight: 6 }}>●</span>
          medisense.ma{url}
        </div>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 9, color: '#64748B',
          letterSpacing: '0.12em', textTransform: 'uppercase',
        }}>{role}</div>
      </div>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>{children}</div>
    </div>
  );
}

function App() {
  const TWEAK_DEFAULS = /*EDITMODE-BEGIN*/{
    "patient_screen": "chat",
    "patient_urgent": true,
    "patient_paired": true
  }/*EDITMODE-END*/;
  const [t, setTweak] = useTweaks(TWEAK_DEFAULS);

  // Patient mobile main app screen (which tab is shown in App artboard)
  const renderPatientScreen = (s) => {
    if (s === 'splash') return <SplashScreen onDone={() => {}}/>;
    if (s === 'onboarding') return <OnboardingScreen onDone={() => {}}/>;
    if (s === 'login') return <LoginScreen onLogin={() => {}}/>;
    if (s === 'consent') return <ConsentScreen onDone={() => {}}/>;
    if (s === 'chat') return <ChatScreen initialUrgent={t.patient_urgent}/>;
    if (s === 'chat_empty') return <ChatScreen initialUrgent={false} initialEmpty/>;
    if (s === 'vitals') return t.patient_paired ? <VitalsScreen/> : <NoDeviceScreen/>;
    if (s === 'agenda') return <AppointmentsScreen/>;
    if (s === 'profile') return <ProfileScreen/>;
    if (s === 'history') return <HistoryScreen/>;
    if (s === 'reminders') return <RemindersScreen/>;
    return null;
  };

  return (
    <>
      <DesignCanvas>
        {/* ─────────── PATIENT MOBILE ─────────── */}
        <DCSection id="patient-flow" title="Patient · Onboarding & Auth"
          subtitle="Flutter mobile · iOS/Android · FR/AR/Darija">
          <DCArtboard id="p-splash" label="01 · Splash" width={320} height={680}>
            <PhoneFrame><SplashScreen onDone={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-onboard" label="02 · Onboarding" width={320} height={680}>
            <PhoneFrame><OnboardingScreen onDone={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-login" label="03 · Login" width={320} height={680}>
            <PhoneFrame><LoginScreen onLogin={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-consent" label="04 · Consentement RGPD" width={320} height={680}>
            <PhoneFrame><ConsentScreen onDone={() => {}}/></PhoneFrame>
          </DCArtboard>
          <DCPostIt x={1320} y={40}>
            Conformité <strong>Loi 09-08</strong> exigée — l'écran consentement est un step bloquant après le login. Toggles distincts par usage (data / IoT / ML / urgence SAMU).
          </DCPostIt>
        </DCSection>

        <DCSection id="patient-app" title="Patient · App principale"
          subtitle="Bottom-tab navigation · streaming RAG · IoT vitals">
          <DCArtboard id="p-chat-empty" label="Chat · empty state" width={320} height={680}>
            <PhoneFrame><ChatScreen initialUrgent={false} initialEmpty/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-chat-urgent" label="Chat · urgence détectée ★" width={320} height={680}>
            <PhoneFrame><ChatScreen initialUrgent/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-vitals" label="Vitaux IoT" width={320} height={680}>
            <PhoneFrame><VitalsScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-vitals-empty" label="Vitaux · pas d'appareil" width={320} height={680}>
            <PhoneFrame><NoDeviceScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-agenda" label="Agenda patient" width={320} height={680}>
            <PhoneFrame><AppointmentsScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-history" label="Historique convos" width={320} height={680}>
            <PhoneFrame><HistoryScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-reminders" label="Rappels traitement" width={320} height={680}>
            <PhoneFrame><RemindersScreen/></PhoneFrame>
          </DCArtboard>
          <DCArtboard id="p-profile" label="Profil patient" width={320} height={680}>
            <PhoneFrame><ProfileScreen/></PhoneFrame>
          </DCArtboard>
          <DCPostIt x={2680} y={40}>
            <strong>★ centerpiece soutenance.</strong> Le chat urgence montre : streaming RAG + scoring confiance + bandeau SAMU 141 + voix. Démo idéale en live.
          </DCPostIt>
        </DCSection>

        {/* ─────────── DOCTOR ─────────── */}
        <DCSection id="doctor" title="Médecin · Web dashboard"
          subtitle="Next.js · console clinique · accès dossier patient assisté IA">
          <DCArtboard id="d-login" label="Login médecin" width={1280} height={800}>
            <BrowserFrame url="/login" role="doctor"><DoctorLogin/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="d-agenda" label="Agenda · risk-coded" width={1280} height={800}>
            <BrowserFrame url="/agenda" role="doctor"><DoctorAgenda/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="d-dpa" label="Résumé DPA · 3-col ★" width={1280} height={800}>
            <BrowserFrame url="/patients/a1b2c3d4" role="doctor"><DoctorDpa/></BrowserFrame>
          </DCArtboard>
          <DCPostIt x={4080} y={40}>
            Le DPA en 3 colonnes (timeline · résumé IA · sources) permet au médecin de valider en 30s. Le Dr. doit pouvoir contredire l'IA — bouton "rejeter" bien visible.
          </DCPostIt>
        </DCSection>

        {/* ─────────── SECRETARY ─────────── */}
        <DCSection id="secretary" title="Secrétaire · Web dashboard"
          subtitle="CRM tâches · feedback ML pour entraînement no-show">
          <DCArtboard id="s-agenda" label="Agenda + feedback" width={1280} height={800}>
            <BrowserFrame url="/agenda" role="secretary"><SecretaryAgenda/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="s-crm" label="CRM tâches IA" width={1280} height={800}>
            <BrowserFrame url="/crm" role="secretary"><SecretaryCrm/></BrowserFrame>
          </DCArtboard>
          <DCPostIt x={2720} y={40}>
            Le feedback "présenté/absent" ferme la boucle d'entraînement XGBoost no-show. C'est l'unique source de label terrain — UX pensée pour 1 clic.
          </DCPostIt>
        </DCSection>

        {/* ─────────── ADMIN ─────────── */}
        <DCSection id="admin" title="Admin · Web dashboard"
          subtitle="RGPD compliance · gestion utilisateurs · evaluation modèles">
          <DCArtboard id="a-audit" label="Logs RGPD ★" width={1280} height={800}>
            <BrowserFrame url="/admin/audit" role="admin"><AdminAudit/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="a-users" label="Utilisateurs" width={1280} height={800}>
            <BrowserFrame url="/admin/users" role="admin"><AdminUsers/></BrowserFrame>
          </DCArtboard>
          <DCArtboard id="a-rerank" label="Évaluation Rerank (BM25 vs Reranker)" width={1280} height={800}>
            <BrowserFrame url="/admin/rerank" role="admin"><AdminRerank/></BrowserFrame>
          </DCArtboard>
          <DCPostIt x={4080} y={40}>
            <strong>★ pièce maîtresse Loi 09-08.</strong> Logs immuables, exportables, chiffrés. Toute action sur donnée nominative = ligne. CNDP-ready.
          </DCPostIt>
        </DCSection>
      </DesignCanvas>

      <TweaksPanel title="Tweaks">
        <TweakSection label="États du Chat patient">
          <TweakToggle label="Urgence détectée (chat)" value={t.patient_urgent} onChange={(v) => setTweak('patient_urgent', v)}/>
          <TweakToggle label="Bracelet IoT appairé" value={t.patient_paired} onChange={(v) => setTweak('patient_paired', v)}/>
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
