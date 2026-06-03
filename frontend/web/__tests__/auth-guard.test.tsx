import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

const mockReplace = vi.fn();
const mockLoadFromStorage = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  usePathname: () => '/',
}));

vi.mock('@/lib/auth', () => ({
  useAuthStore: () => ({ loadFromStorage: mockLoadFromStorage }),
}));

import { AuthGuard } from '@/components/auth-guard';

describe('AuthGuard', () => {
  beforeEach(() => {
    localStorage.clear();
    mockReplace.mockClear();
    mockLoadFromStorage.mockClear();
  });

  it('redirects to /login when no token', () => {
    mockLoadFromStorage.mockReturnValue(Promise.resolve());

    render(
      <AuthGuard>
        <div>Protected</div>
      </AuthGuard>,
    );

    expect(mockReplace).toHaveBeenCalledWith('/login');
  });

  it('renders children after loadFromStorage resolves', async () => {
    localStorage.setItem('access_token', 'tok');
    mockLoadFromStorage.mockReturnValue(Promise.resolve());

    await act(async () => {
      render(
        <AuthGuard>
          <div>Protected Content</div>
        </AuthGuard>,
      );
    });

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it('shows loading state while loading', () => {
    localStorage.setItem('access_token', 'tok');
    // Never-resolving promise to keep loading state
    mockLoadFromStorage.mockReturnValue(new Promise(() => {}));

    render(
      <AuthGuard>
        <div>Protected</div>
      </AuthGuard>,
    );

    // Children should not be visible yet
    expect(screen.queryByText('Protected')).not.toBeInTheDocument();
  });
});
