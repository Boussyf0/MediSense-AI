// Lightweight stroke icon set for MediSense
// All icons share size/stroke API: <Icon size={20} stroke={1.6} color="currentColor" />

const Ico = ({ size = 22, stroke = 1.6, color = 'currentColor', children, style }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"
    style={style}>{children}</svg>
);

const IconChat = (p) => <Ico {...p}><path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.7-5.2A8 8 0 1 1 21 12Z"/></Ico>;
const IconHeart = (p) => <Ico {...p}><path d="M12 21s-7-4.5-9.5-9A5.5 5.5 0 0 1 12 6a5.5 5.5 0 0 1 9.5 6c-2.5 4.5-9.5 9-9.5 9Z"/></Ico>;
const IconActivity = (p) => <Ico {...p}><path d="M3 12h4l2-7 4 14 2-7h6"/></Ico>;
const IconCalendar = (p) => <Ico {...p}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></Ico>;
const IconUser = (p) => <Ico {...p}><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></Ico>;
const IconBack = (p) => <Ico {...p}><path d="M15 18l-6-6 6-6"/></Ico>;
const IconMore = (p) => <Ico {...p}><circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/></Ico>;
const IconMic = (p) => <Ico {...p}><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></Ico>;
const IconSend = (p) => <Ico {...p}><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z"/></Ico>;
const IconLock = (p) => <Ico {...p}><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></Ico>;
const IconShield = (p) => <Ico {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></Ico>;
const IconBell = (p) => <Ico {...p}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></Ico>;
const IconChevron = (p) => <Ico {...p}><path d="M9 6l6 6-6 6"/></Ico>;
const IconCheck = (p) => <Ico {...p}><path d="M5 12l5 5L20 7"/></Ico>;
const IconAlert = (p) => <Ico {...p}><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0Z"/></Ico>;
const IconBluetooth = (p) => <Ico {...p}><path d="m7 7 10 10-5 5V2l5 5L7 17"/></Ico>;
const IconSparkles = (p) => <Ico {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></Ico>;
const IconSettings = (p) => <Ico {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></Ico>;
const IconGlobe = (p) => <Ico {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></Ico>;
const IconLogout = (p) => <Ico {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></Ico>;
const IconPill = (p) => <Ico {...p}><rect x="2" y="8" width="20" height="8" rx="4" transform="rotate(-25 12 12)"/><path d="m9.5 6.3 8.2 11.4" transform="rotate(-25 12 12)"/></Ico>;
const IconQR = (p) => <Ico {...p}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3M21 17v4h-4M14 21h3"/></Ico>;
const IconClose = (p) => <Ico {...p}><path d="M18 6 6 18M6 6l12 12"/></Ico>;
const IconEye = (p) => <Ico {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></Ico>;
const IconLung = (p) => <Ico {...p}><path d="M6.1 22a3.5 3.5 0 0 1-3.5-3.5V14c0-3 2-5.5 4.5-7l1.4-.8a2 2 0 0 1 3 1.7V18a4 4 0 0 1-4 4H6.1ZM17.9 22a3.5 3.5 0 0 0 3.5-3.5V14c0-3-2-5.5-4.5-7l-1.4-.8a2 2 0 0 0-3 1.7V18a4 4 0 0 0 4 4h1.4Z"/><path d="M12 4v8"/></Ico>;
const IconWave = (p) => <Ico {...p}><path d="M2 12h2l2-7 3 14 3-10 3 7 3-4h4"/></Ico>;
const IconStethoscope = (p) => <Ico {...p}><path d="M6 3v8a4 4 0 0 0 8 0V3M4 3h4M12 3h4M10 15v3a4 4 0 0 0 8 0v-1"/><circle cx="18" cy="14" r="2"/></Ico>;
const IconHistory = (p) => <Ico {...p}><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2"/></Ico>;
const IconLanguage = (p) => <Ico {...p}><path d="M3 5h12M9 3v2c0 6-3 8-6 8M5 9c0 4 4 6 8 6M14 21l4-10 4 10M16 18h4"/></Ico>;
const IconTrash = (p) => <Ico {...p}><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M6 6l1 14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-14"/></Ico>;
const IconDoc = (p) => <Ico {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></Ico>;
const IconLink = (p) => <Ico {...p}><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></Ico>;

Object.assign(window, {
  IconChat, IconHeart, IconActivity, IconCalendar, IconUser,
  IconBack, IconMore, IconMic, IconSend, IconLock, IconShield, IconBell,
  IconChevron, IconCheck, IconAlert, IconBluetooth, IconSparkles, IconSettings,
  IconGlobe, IconLogout, IconPill, IconQR, IconClose, IconEye, IconLung,
  IconWave, IconStethoscope, IconHistory, IconLanguage, IconTrash, IconDoc, IconLink,
});
