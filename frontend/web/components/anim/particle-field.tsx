'use client';
import { useEffect, useState } from 'react';

interface Props {
  count?: number;
  color?: string;
}

interface Particle {
  i: number;
  left: number;
  top: number;
  size: number;
  dx: number;
  dy: number;
  delay: number;
  duration: number;
}

export function ParticleField({ count = 24, color = 'rgba(139,92,246,0.45)' }: Props) {
  const [particles, setParticles] = useState<Particle[]>([]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setParticles(
      Array.from({ length: count }).map((_, i) => ({
        i,
        left: Math.random() * 100,
        top: 60 + Math.random() * 40,
        size: 2 + Math.random() * 3,
        dx: (Math.random() - 0.5) * 80,
        dy: -60 - Math.random() * 120,
        delay: Math.random() * 6,
        duration: 6 + Math.random() * 4,
      })),
    );
  }, [count]);

  return (
    <div
      aria-hidden
      style={{
        position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none',
      }}
    >
      {particles.map((p) => (
        <span
          key={p.i}
          style={{
            position: 'absolute',
            left: `${p.left}%`, top: `${p.top}%`,
            width: p.size, height: p.size, borderRadius: '50%',
            background: color,
            animation: `drift ${p.duration}s linear infinite`,
            animationDelay: `${p.delay}s`,
            ['--dx' as string]: `${p.dx}px`,
            ['--dy' as string]: `${p.dy}px`,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}
