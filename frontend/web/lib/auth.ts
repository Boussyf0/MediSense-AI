import { create } from 'zustand';
import { api } from './api';

interface User {
  uuid: string;
  email: string;
  role: 'doctor' | 'secretary' | 'admin' | 'patient';
  first_name?: string;
  last_name?: string;
}

interface AuthStore {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadFromStorage: () => Promise<void>;
}

export const roleDefaultPath = (role: string) =>
  role === 'admin' ? '/admin/audit-logs' : '/agenda';

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: null,

  login: async (email, password) => {
    // Refresh token is set as httpOnly cookie by the backend — no localStorage needed
    const { data: tokens } = await api.post('/auth/login', { email, password });
    localStorage.setItem('access_token', tokens.access_token);
    const { data: raw } = await api.get('/auth/me');
    set({ user: { ...raw, uuid: raw.user_uuid ?? raw.uuid }, token: tokens.access_token });
  },

  logout: async () => {
    try { await api.post('/auth/logout'); } catch (err) { console.error('Logout failed:', err); }
    localStorage.removeItem('access_token');
    set({ user: null, token: null });
  },

  loadFromStorage: async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (!token) return;
    try {
      const { data: raw } = await api.get('/auth/me');
      set({ user: { ...raw, uuid: raw.user_uuid ?? raw.uuid }, token });
    } catch (err) {
      console.error('Session restore failed:', err);
      localStorage.removeItem('access_token');
    }
  },
}));
