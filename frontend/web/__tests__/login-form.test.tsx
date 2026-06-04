import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const mockReplace = vi.fn();
const mockLogin = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
}));

vi.mock('next/image', () => ({
  default: (props: Record<string, unknown>) => {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
    const { priority, ...rest } = props;
    return <img {...(rest as React.ImgHTMLAttributes<HTMLImageElement>)} />;
  },
}));

vi.mock('@/lib/auth', () => ({
  useAuthStore: Object.assign(
    () => ({ login: mockLogin }),
    {
      getState: () => ({
        user: { role: 'doctor' },
      }),
    },
  ),
  roleDefaultPath: (role: string) =>
    role === 'admin' ? '/admin/audit-logs' : '/agenda',
}));

vi.mock('@/components/icons', () => ({
  IconEye: () => <span data-testid="icon-eye" />,
}));

import LoginPage from '@/app/login/page';

describe('LoginPage', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    mockLogin.mockClear();
  });

  it('renders email and password inputs', () => {
    render(<LoginPage />);
    expect(
      screen.getByPlaceholderText('dr.merrouni@clinique.ma'),
    ).toBeInTheDocument();
    expect(screen.getByText('Se connecter')).toBeInTheDocument();
  });

  it('shows error message on failed login', async () => {
    mockLogin.mockRejectedValueOnce({
      response: { data: { detail: 'Email ou mot de passe incorrect' } },
    });

    render(<LoginPage />);
    const emailInput = screen.getByPlaceholderText('dr.merrouni@clinique.ma');
    const form = emailInput.closest('form')!;

    fireEvent.change(emailInput, { target: { value: 'bad@x.com' } });
    // Find password input by type
    const passwordInput = form.querySelector('input[type="password"]')!;
    fireEvent.change(passwordInput, { target: { value: 'wrong' } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(
        screen.getByText('Email ou mot de passe incorrect'),
      ).toBeInTheDocument();
    });
  });

  it('calls login with form values', async () => {
    mockLogin.mockResolvedValueOnce(undefined);

    render(<LoginPage />);
    const emailInput = screen.getByPlaceholderText('dr.merrouni@clinique.ma');
    const form = emailInput.closest('form')!;

    fireEvent.change(emailInput, { target: { value: 'dr@clinic.ma' } });
    const passwordInput = form.querySelector('input[type="password"]')!;
    fireEvent.change(passwordInput, { target: { value: 'secret' } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('dr@clinic.ma', 'secret');
    });
  });

  it('shows loading state during submit', async () => {
    // Login that never resolves
    mockLogin.mockReturnValue(new Promise(() => {}));

    render(<LoginPage />);
    const emailInput = screen.getByPlaceholderText('dr.merrouni@clinique.ma');
    const form = emailInput.closest('form')!;

    fireEvent.change(emailInput, { target: { value: 'dr@clinic.ma' } });
    const passwordInput = form.querySelector('input[type="password"]')!;
    fireEvent.change(passwordInput, { target: { value: 'pass' } });
    fireEvent.submit(form);

    await waitFor(() => {
      const submitBtn = form.querySelector('button[type="submit"]')!;
      expect(submitBtn).toBeDisabled();
    });
  });
});
