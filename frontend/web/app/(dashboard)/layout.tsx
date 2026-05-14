'use client';
import { Sidebar } from '@/components/sidebar';
import { AuthGuard } from '@/components/auth-guard';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--s0)' }}>
        <Sidebar />
        <main style={{ flex: 1, overflow: 'auto', minHeight: '100vh' }}>
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
