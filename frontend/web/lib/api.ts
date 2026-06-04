import axios from 'axios';

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// withCredentials: true sends httpOnly cookies (refresh_token) automatically
export const api = axios.create({ baseURL: BASE, withCredentials: true });

const refreshApi = axios.create({ baseURL: BASE, withCredentials: true });

api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  if (token) config.headers['Authorization'] = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status !== 401) return Promise.reject(error);
    try {
      // Refresh token is sent automatically via httpOnly cookie
      const { data } = await refreshApi.post('/auth/refresh');
      localStorage.setItem('access_token', data.access_token);
      error.config.headers['Authorization'] = `Bearer ${data.access_token}`;
      return api(error.config);
    } catch (refreshErr) {
      console.error('Token refresh failed:', refreshErr);
      localStorage.removeItem('access_token');
      if (typeof window !== 'undefined') window.location.href = '/login';
      return Promise.reject(error);
    }
  }
);
