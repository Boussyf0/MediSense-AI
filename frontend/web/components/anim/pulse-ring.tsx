'use client';
import type { CSSProperties } from 'react';

interface Props {
  color?: string;
  size?: number;
  rings?: number;
  style?: CSSProperties;
}

export function PulseRing({ color = '#6366F1', size = 56, rings = 3, style }: Props) {
  return (
    <div style={{
      position: 'relative', width: size, height: size, ...style,
    }}>
      {Array.from({ length: rings }).map((_, i) => (
        <span key={i} style={{
          position: 'absolute', inset: 0, borderRadius: '50%',
          border: `2px solid ${color}`,
          animation: 'pulse-ring 1.5s ease-out infinite',
          animationDelay: `${i * 0.4}s`,
        }} />
      ))}
    </div>
  );
}
