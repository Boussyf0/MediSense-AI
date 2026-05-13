'use client';
import type { ReactNode } from 'react';

interface TopBarProps {
  title: string;
  subtitle?: string;
  breadcrumb?: string;
  actions?: ReactNode;
}

export function DashTopBar({ title, subtitle, breadcrumb, actions }: TopBarProps) {
  return (
    <div style={{
      padding: '20px 28px 18px',
      borderBottom: '1px solid var(--line)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16,
      background: 'rgba(15, 22, 35, 0.3)',
    }}>
      <div style={{ minWidth: 0 }}>
        {breadcrumb && (
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t4)',
            letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6,
          }}>
            {breadcrumb}
          </div>
        )}
        <h1 style={{
          fontFamily: 'var(--f-display)', fontWeight: 600, fontSize: 22,
          color: 'var(--t0)', margin: 0, letterSpacing: '-0.01em',
        }}>
          {title}
        </h1>
        {subtitle && (
          <div style={{ color: 'var(--t2)', fontSize: 12.5, marginTop: 4 }}>{subtitle}</div>
        )}
      </div>
      {actions && (
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>{actions}</div>
      )}
    </div>
  );
}

interface PageProps extends TopBarProps {
  children: ReactNode;
}

export function DashPage({ title, subtitle, breadcrumb, actions, children }: PageProps) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', minHeight: '100vh',
      background: 'var(--s0)', color: 'var(--t0)',
    }}>
      <DashTopBar title={title} subtitle={subtitle} breadcrumb={breadcrumb} actions={actions} />
      <div className="scroll-hide" style={{ flex: 1, overflowY: 'auto', padding: '22px 28px' }}>
        {children}
      </div>
    </div>
  );
}
