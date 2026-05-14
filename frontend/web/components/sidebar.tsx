'use client';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/auth';
import {
  IconCalendar, IconUsers, IconDoc, IconSync, IconCheck,
  IconShield, IconFlask, IconCpu, IconLogout,
} from './icons';
import type { IconProps } from './icons';

type Role = 'doctor' | 'secretary' | 'admin';

interface NavItem {
  key: string;
  href: string;
  label: string;
  icon: (p: IconProps) => React.ReactElement;
}

const NAV: Record<Role, NavItem[]> = {
  doctor: [
    { key: 'agenda',   href: '/agenda',   label: 'Agenda',       icon: IconCalendar },
    { key: 'patients', href: '/patients', label: 'Patients',     icon: IconUsers },
    { key: 'dpa',      href: '/dpa',      label: 'Résumés DPA',  icon: IconDoc },
  ],
  secretary: [
    { key: 'agenda',   href: '/agenda',     label: 'Agenda',       icon: IconCalendar },
    { key: 'crm',      href: '/crm/tasks',  label: 'Tâches CRM',   icon: IconSync },
    { key: 'feedback', href: '/feedback',   label: 'Feedback ML',  icon: IconCheck },
  ],
  admin: [
    { key: 'audit',  href: '/admin/audit-logs', label: 'Logs RGPD',     icon: IconShield },
    { key: 'users',  href: '/admin/users',      label: 'Utilisateurs',  icon: IconUsers },
    { key: 'rerank', href: '/admin/rerank',     label: 'Rerank Eval',   icon: IconFlask },
    { key: 'system', href: '/admin/system',     label: 'Système',       icon: IconCpu },
  ],
};

const ROLE_SUBTITLE: Record<Role, string> = {
  doctor:    'console clinique',
  secretary: 'console secrétariat',
  admin:     'console admin',
};

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const role = ((user?.role === 'patient' ? 'doctor' : user?.role) ?? 'doctor') as Role;
  const items = NAV[role];

  const initial = user
    ? (user.first_name?.[0] ?? user.email[0]).toUpperCase()
    : '?';
  const fullName = user?.first_name
    ? `${user.first_name} ${user.last_name ?? ''}`.trim()
    : user?.email ?? 'Utilisateur';

  const handleLogout = async () => { await logout(); router.replace('/login'); };

  return (
    <aside
      className="scroll-hide"
      style={{
        width: 220, flexShrink: 0,
        background: 'var(--s1)',
        borderRight: '1px solid var(--line)',
        display: 'flex', flexDirection: 'column',
        height: '100vh', position: 'sticky', top: 0,
      }}
    >
      {/* logo */}
      <div style={{ padding: '20px 18px 18px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <Image
            src="/logo.png"
            alt="MediSense AI"
            width={24}
            height={24}
            style={{ borderRadius: 6, flexShrink: 0 }}
          />
          <div style={{
            fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 14,
            color: 'var(--t0)', letterSpacing: '-0.01em',
          }}>
            MediSense<span className="grad-text"> AI</span>
          </div>
        </div>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
          letterSpacing: '0.16em', textTransform: 'uppercase', marginTop: 4,
        }}>
          {ROLE_SUBTITLE[role]}
        </div>
      </div>

      {/* nav */}
      <nav className="scroll-hide" style={{ flex: 1, padding: '14px 10px', overflowY: 'auto' }}>
        <div style={{
          fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t4)',
          letterSpacing: '0.16em', textTransform: 'uppercase',
          padding: '6px 8px 8px',
        }}>
          Navigation
        </div>
        {items.map(({ key, href, label, icon: Icon }) => {
          const isActive = pathname === href || pathname.startsWith(href + '/');
          return (
            <button
              key={key}
              onClick={() => router.push(href)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                padding: '9px 10px', marginBottom: 2,
                background: isActive ? 'var(--s2)' : 'transparent',
                border: 'none',
                borderLeft: `2px solid ${isActive ? '#8B5CF6' : 'transparent'}`,
                color: isActive ? 'var(--t0)' : 'var(--t2)',
                fontFamily: 'var(--f-body)', fontSize: 13,
                fontWeight: isActive ? 500 : 400,
                cursor: 'pointer', textAlign: 'left', borderRadius: 6,
                transition: 'all .15s',
              }}
            >
              <Icon size={18} stroke={1.7} color={isActive ? '#A78BFA' : '#64748B'} />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      {/* user */}
      <div style={{
        borderTop: '1px solid var(--line)', padding: '12px 14px',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 99,
          background: 'var(--ai-grad)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--f-display)', fontSize: 13, fontWeight: 600, color: '#fff',
          flexShrink: 0,
        }}>
          {initial}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontFamily: 'var(--f-body)', fontSize: 12, fontWeight: 500, color: 'var(--t0)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {fullName}
          </div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 9, color: 'var(--t3)',
            textTransform: 'uppercase', letterSpacing: '0.12em',
          }}>
            {role}
          </div>
        </div>
        <button
          title="Déconnexion"
          onClick={handleLogout}
          style={{
            background: 'transparent', border: '1px solid var(--line)', color: 'var(--t3)',
            width: 26, height: 26, borderRadius: 6, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <IconLogout size={13} stroke={2} />
        </button>
      </div>
    </aside>
  );
}
