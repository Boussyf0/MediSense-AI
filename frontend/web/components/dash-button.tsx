'use client';
import { ReactNode } from 'react';

interface Props {
  children: ReactNode;
  onClick?: () => void;
  kind?: 'gradient' | 'solid' | 'ghost';
  icon?: ReactNode;
  small?: boolean;
  disabled?: boolean;
  danger?: boolean;
  type?: 'button' | 'submit';
  loading?: boolean;
}

export function DashButton({
  children, onClick, kind = 'ghost', icon, small, disabled, danger, type = 'button', loading,
}: Props) {
  const padY = small ? 6 : 8;
  const padX = small ? 11 : 14;
  const fs = small ? 11.5 : 12.5;

  let style: React.CSSProperties;
  if (kind === 'gradient') {
    style = {
      background: 'var(--ai-grad)',
      color: '#fff',
      border: 'none',
      boxShadow: '0 4px 16px rgba(99,102,241,0.30)',
    };
  } else if (kind === 'solid') {
    style = {
      background: danger ? 'rgba(239,68,68,0.12)' : 'var(--s2)',
      color: danger ? '#FCA5A5' : 'var(--t0)',
      border: `1px solid ${danger ? 'rgba(239,68,68,0.40)' : 'var(--line-strong)'}`,
    };
  } else {
    style = {
      background: 'transparent',
      color: 'var(--t1)',
      border: '1px solid var(--line)',
    };
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        ...style,
        padding: `${padY}px ${padX}px`, borderRadius: 8,
        fontFamily: 'var(--f-body)', fontSize: fs, fontWeight: 500,
        cursor: disabled || loading ? 'default' : 'pointer',
        display: 'inline-flex', alignItems: 'center', gap: 7,
        whiteSpace: 'nowrap', transition: 'transform .12s, box-shadow .12s',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {loading ? (
        <span style={{
          width: 12, height: 12, borderRadius: '50%',
          border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff',
          animation: 'spin 0.8s linear infinite',
        }} />
      ) : icon}
      {children}
    </button>
  );
}
