'use client';
import { useEffect, useRef, useState } from 'react';

interface Props {
  value: number;
  duration?: number;
  decimals?: number;
  format?: (n: number) => string;
}

export function CountUp({ value, duration = 900, decimals = 0, format }: Props) {
  const [n, setN] = useState(0);
  const fromRef = useRef(0);
  const startRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    fromRef.current = n;
    startRef.current = null;
    const target = value;
    const tick = (ts: number) => {
      if (startRef.current === null) startRef.current = ts;
      const elapsed = ts - startRef.current;
      const t = Math.min(1, elapsed / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = fromRef.current + (target - fromRef.current) * eased;
      setN(next);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, duration]);

  const display = format ? format(n) : n.toFixed(decimals);
  return <>{display}</>;
}
