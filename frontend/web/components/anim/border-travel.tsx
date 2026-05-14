'use client';
import type { CSSProperties, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  active?: boolean;
  radius?: number;
  style?: CSSProperties;
}

export function BorderTravel({ children, active = true, radius = 12, style }: Props) {
  return (
    <div style={{ position: 'relative', borderRadius: radius, ...style }}>
      {active && (
        <span
          aria-hidden
          style={{
            position: 'absolute', left: 0, width: 3, height: '40%',
            background: 'var(--ai-grad)',
            borderRadius: 3,
            animation: 'border-travel 3s linear infinite',
            pointerEvents: 'none',
          }}
        />
      )}
      {children}
    </div>
  );
}
