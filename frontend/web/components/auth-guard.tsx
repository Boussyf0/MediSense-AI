'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/auth';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { loadFromStorage } = useAuthStore();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) { router.replace('/login'); return; }
    loadFromStorage().finally(() => setReady(true));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!ready) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--s0)' }}>
        <div style={{ display: 'flex', gap: 5 }}>
          {[0, 1, 2].map(i => (
            <span key={i} style={{
              width: 8, height: 8, borderRadius: '50%', background: '#6366F1',
              animation: `typing-dot 1.2s ease ${i * 0.15}s infinite`,
              display: 'inline-block',
            }} />
          ))}
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
