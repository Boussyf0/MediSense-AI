'use client';
import { useState } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { useAuthStore, roleDefaultPath } from '@/lib/auth';
import { IconEye } from '@/components/icons';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [focusEmail, setFocusEmail] = useState(false);
  const [focusPw, setFocusPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [shake, setShake] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(email, password);
      const { user } = useAuthStore.getState();
      router.replace(roleDefaultPath(user?.role ?? 'doctor'));
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Email ou mot de passe incorrect';
      setError(msg);
      setShake(true);
      setTimeout(() => setShake(false), 400);
    } finally {
      setLoading(false);
    }
  };

  const subtitle =
    email.includes('admin')
      ? 'Accès administrateur'
      : email.includes('secretary') || email.includes('sec')
        ? 'Accès secrétaire · authentification SSO'
        : 'Accès médecin · authentification SSO';

  const inputBase: React.CSSProperties = {
    width: '100%', padding: '11px 13px',
    background: 'var(--s2)',
    border: 'none',
    borderBottom: '1px solid var(--line-strong)',
    borderRadius: '8px 8px 0 0',
    color: 'var(--t0)',
    fontFamily: 'var(--f-body)', fontSize: 13.5,
    outline: 'none', boxSizing: 'border-box',
  };

  const underline = (focused: boolean): React.CSSProperties => ({
    position: 'absolute', bottom: 0, left: 0, right: 0,
    height: 2, borderRadius: 99,
    background: 'var(--ai-grad)',
    transform: focused ? 'scaleX(1)' : 'scaleX(0)',
    transformOrigin: 'left',
    transition: 'transform .25s ease',
    boxShadow: focused ? '0 0 12px rgba(139,92,246,0.5)' : 'none',
  });

  return (
    <div style={{
      width: '100%', minHeight: '100vh', position: 'relative', overflow: 'hidden',
      background: 'var(--s0)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--f-body)',
    }}>
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background:
          'radial-gradient(700px 400px at 70% 30%, rgba(99,102,241,0.10), transparent 60%), ' +
          'radial-gradient(500px 400px at 20% 80%, rgba(139,92,246,0.07), transparent 60%)',
      }} />

      <div style={{ width: 420, position: 'relative', zIndex: 1, padding: '0 16px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ display: 'inline-flex', justifyContent: 'center', marginBottom: 12 }}>
            <Image
              src="/logo.png"
              alt="MediSense AI"
              width={64}
              height={64}
              priority
              style={{ borderRadius: 16 }}
            />
          </div>
          <div style={{
            fontFamily: 'var(--f-display)', fontSize: 22, fontWeight: 600,
            letterSpacing: '-0.01em', color: 'var(--t0)',
          }}>
            MediSense<span className="grad-text"> AI</span>
          </div>
          <div style={{
            fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
            letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 4,
          }}>
            Console clinique
          </div>
        </div>

        {/* Card */}
        <div style={{
          background: 'var(--s1)', border: '1px solid var(--line)',
          borderRadius: 16, padding: 28,
          boxShadow: '0 12px 48px rgba(0,0,0,0.4)',
          animation: shake ? 'shake 0.4s ease' : 'none',
        }}>
          <form onSubmit={handleSubmit}>
            <h2 style={{
              fontFamily: 'var(--f-display)', fontSize: 24, fontWeight: 600,
              margin: '0 0 4px', color: 'var(--t0)', letterSpacing: '-0.01em',
            }}>
              Connexion
            </h2>
            <div style={{ color: 'var(--t2)', fontSize: 13, marginBottom: 22 }}>
              {subtitle}
            </div>

            {error && (
              <div style={{
                padding: '10px 14px', borderRadius: 8, marginBottom: 16,
                background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.40)',
                color: '#EF4444', fontSize: 13,
              }}>
                {error}
              </div>
            )}

            {/* Email */}
            <div style={{ marginBottom: 16 }}>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6,
              }}>
                Email professionnel
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onFocus={() => setFocusEmail(true)}
                  onBlur={() => setFocusEmail(false)}
                  required
                  autoComplete="email"
                  placeholder="dr.merrouni@clinique.ma"
                  style={inputBase}
                />
                <div style={underline(focusEmail)} />
              </div>
            </div>

            {/* Password */}
            <div style={{ marginBottom: 22 }}>
              <div style={{
                fontFamily: 'var(--f-mono)', fontSize: 9.5, color: 'var(--t3)',
                letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6,
              }}>
                Mot de passe
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onFocus={() => setFocusPw(true)}
                  onBlur={() => setFocusPw(false)}
                  required
                  autoComplete="current-password"
                  style={{ ...inputBase, padding: '11px 40px 11px 13px' }}
                />
                <div style={underline(focusPw)} />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  aria-label={showPw ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                  style={{
                    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
                    background: 'transparent', border: 'none', color: 'var(--t3)',
                    cursor: 'pointer',
                    width: 24, height: 24,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <IconEye size={14} stroke={2} />
                </button>
              </div>
              <div style={{
                marginTop: 8, fontFamily: 'var(--f-mono)', fontSize: 10, color: 'var(--t3)',
              }}>
                <a href="#" style={{ color: '#A78BFA', textDecoration: 'none' }}>
                  Mot de passe oublié ?
                </a>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '12px', borderRadius: 99,
                background: 'var(--ai-grad)', color: '#fff', border: 'none',
                fontFamily: 'var(--f-body)', fontSize: 14, fontWeight: 600,
                cursor: loading ? 'default' : 'pointer',
                boxShadow: '0 8px 24px rgba(99,102,241,0.30)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                opacity: loading ? 0.8 : 1, transition: 'opacity 0.15s',
              }}
            >
              {loading ? (
                <span style={{ display: 'inline-flex', gap: 4 }}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      style={{
                        width: 6, height: 6, borderRadius: '50%', background: '#fff',
                        animation: `typing-dot 1.4s ease ${i * 0.15}s infinite`,
                      }}
                    />
                  ))}
                </span>
              ) : (
                <>
                  Se connecter
                  <span>→</span>
                </>
              )}
            </button>
          </form>
        </div>

        <div style={{
          textAlign: 'center', marginTop: 18,
          fontFamily: 'var(--f-mono)', fontSize: 9.5,
          color: 'var(--t4)', letterSpacing: '0.14em', textTransform: 'uppercase',
        }}>
          v1.0 · n.synergy · EMSI Marrakech
        </div>
      </div>
    </div>
  );
}
