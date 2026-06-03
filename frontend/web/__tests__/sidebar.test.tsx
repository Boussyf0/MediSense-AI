import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

const mockLogout = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => '/agenda',
}));

vi.mock('next/image', () => ({
  default: (props: Record<string, unknown>) => {
    const { priority, ...rest } = props;
    return <img {...(rest as React.ImgHTMLAttributes<HTMLImageElement>)} />;
  },
}));

let mockUser = { role: 'doctor', email: 'dr@clinic.ma', first_name: 'Ahmed', last_name: 'Merrouni' };

vi.mock('@/lib/auth', () => ({
  useAuthStore: () => ({
    user: mockUser,
    logout: mockLogout,
  }),
}));

vi.mock('@/components/AlertsProvider', () => ({
  useAlerts: () => ({ unread: 0, openFeed: vi.fn() }),
}));

// Stub all icon components
vi.mock('@/components/icons', () => {
  const stub = (props: { size?: number }) => <span data-testid="icon" />;
  return {
    IconCalendar: stub,
    IconUsers: stub,
    IconDoc: stub,
    IconSync: stub,
    IconCheck: stub,
    IconShield: stub,
    IconFlask: stub,
    IconCpu: stub,
    IconLogout: stub,
    IconBell: stub,
  };
});

import { Sidebar } from '@/components/sidebar';

describe('Sidebar', () => {
  beforeEach(() => {
    mockLogout.mockClear();
  });

  it('doctor sees Agenda, Patients, Résumés DPA', () => {
    mockUser = { role: 'doctor', email: 'dr@clinic.ma', first_name: 'Ahmed', last_name: 'Merrouni' };
    render(<Sidebar />);
    expect(screen.getByText('Agenda')).toBeInTheDocument();
    expect(screen.getByText('Patients')).toBeInTheDocument();
    expect(screen.getByText('Résumés DPA')).toBeInTheDocument();
  });

  it('admin sees Logs RGPD, Utilisateurs, Rerank Eval, Système', () => {
    mockUser = { role: 'admin', email: 'admin@clinic.ma', first_name: 'Admin', last_name: '' };
    render(<Sidebar />);
    expect(screen.getByText('Logs RGPD')).toBeInTheDocument();
    expect(screen.getByText('Utilisateurs')).toBeInTheDocument();
    expect(screen.getByText('Rerank Eval')).toBeInTheDocument();
    expect(screen.getByText('Système')).toBeInTheDocument();
  });

  it('secretary sees Agenda, Tâches CRM, Feedback ML', () => {
    mockUser = { role: 'secretary', email: 'sec@clinic.ma', first_name: 'Sara', last_name: '' };
    render(<Sidebar />);
    expect(screen.getByText('Agenda')).toBeInTheDocument();
    expect(screen.getByText('Tâches CRM')).toBeInTheDocument();
    expect(screen.getByText('Feedback ML')).toBeInTheDocument();
  });
});
