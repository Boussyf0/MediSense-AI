'use client';
import { useEffect, useState } from 'react';

interface Props {
  value: number;
  label?: string;
  width?: number | string;
}

export function ConfidenceBar({ value, label = 'Confiance', width = 160 }: Props) {
  const [animated, setAnimated] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setAnimated(value), 50);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      {label && (
        <span style={{
          fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t2)',
          letterSpacing: '0.08em', textTransform: 'uppercase',
        }}>
          {label}
        </span>
      )}
      <div style={{
        width, height: 5, background: 'var(--s3)',
        borderRadius: 99, overflow: 'hidden',
      }}>
        <div style={{
          width: `${animated * 100}%`, height: '100%',
          background: 'var(--ai-grad)',
          borderRadius: 99, transition: 'width .8s ease-out',
        }} />
      </div>
      <span style={{
        fontFamily: 'var(--f-mono)', fontSize: 11, color: 'var(--t0)', fontWeight: 600,
      }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}
