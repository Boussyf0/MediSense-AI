import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAuthStore, roleDefaultPath } from '@/lib/auth';

vi.mock('@/lib/api', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '@/lib/api';

const mockUser = {
  user_uuid: 'uuid-abc',
  email: 'dr@clinic.ma',
  role: 'doctor' as const,
  first_name: 'Ahmed',
  last_name: 'Merrouni',
};

describe('useAuthStore', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, token: null });
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('login sets user and token', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: { access_token: 'tok-123' },
    } as never);
    vi.mocked(api.get).mockResolvedValueOnce({
      data: mockUser,
    } as never);

    await useAuthStore.getState().login('dr@clinic.ma', 'pass');

    const state = useAuthStore.getState();
    expect(state.token).toBe('tok-123');
    expect(state.user).not.toBeNull();
    expect(state.user!.email).toBe('dr@clinic.ma');
    expect(state.user!.uuid).toBe('uuid-abc');
  });

  it('login stores access_token in localStorage', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: { access_token: 'tok-456' },
    } as never);
    vi.mocked(api.get).mockResolvedValueOnce({
      data: mockUser,
    } as never);

    await useAuthStore.getState().login('dr@clinic.ma', 'pass');
    expect(localStorage.getItem('access_token')).toBe('tok-456');
  });

  it('logout clears state and storage', async () => {
    // Seed state
    useAuthStore.setState({
      user: { uuid: 'x', email: 'x@x.ma', role: 'doctor' },
      token: 'tok',
    });
    localStorage.setItem('access_token', 'tok');

    vi.mocked(api.post).mockResolvedValueOnce({} as never);

    await useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('loadFromStorage restores session', async () => {
    localStorage.setItem('access_token', 'tok-existing');
    vi.mocked(api.get).mockResolvedValueOnce({
      data: mockUser,
    } as never);

    await useAuthStore.getState().loadFromStorage();

    const state = useAuthStore.getState();
    expect(state.user).not.toBeNull();
    expect(state.user!.role).toBe('doctor');
    expect(state.token).toBe('tok-existing');
  });

  it('loadFromStorage clears on failure', async () => {
    localStorage.setItem('access_token', 'tok-expired');
    vi.mocked(api.get).mockRejectedValueOnce(new Error('401'));

    await useAuthStore.getState().loadFromStorage();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});

describe('roleDefaultPath', () => {
  it('returns /admin/audit-logs for admin', () => {
    expect(roleDefaultPath('admin')).toBe('/admin/audit-logs');
  });

  it('returns /agenda for other roles', () => {
    expect(roleDefaultPath('doctor')).toBe('/agenda');
    expect(roleDefaultPath('secretary')).toBe('/agenda');
  });
});
