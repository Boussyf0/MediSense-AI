import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'surface-0': '#0A0D14',
        'surface-1': '#111827',
        'surface-2': '#1C2333',
        'surface-3': '#252D40',
        'ai-from': '#6366F1',
        'ai-to': '#8B5CF6',
        'risk-safe': '#22C55E',
        'risk-warn': '#F97316',
        'risk-danger': '#EF4444',
        pulse: '#F43F5E',
        oxy: '#38BDF8',
        hrv: '#A78BFA',
        t0: '#F8FAFC',
        t1: '#CBD5E1',
        t2: '#94A3B8',
        t3: '#64748B',
        t4: '#475569',
      },
      fontFamily: {
        display: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'Menlo', 'monospace'],
      },
      backgroundImage: {
        'ai-grad': 'linear-gradient(135deg, #6366F1, #8B5CF6)',
        'ai-grad-soft': 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(139,92,246,0.18))',
      },
      animation: {
        'wave-bar': 'wave-bar 1.4s ease-in-out infinite',
        drift: 'drift 8s linear infinite',
        'bubble-in': 'bubble-in 0.25s ease',
        'border-travel': 'border-travel 3s linear infinite',
        'streaming-cursor': 'streaming-cursor 1s ease-in-out infinite',
        'typing-dot': 'typing-dot 1.4s ease infinite',
        'pulse-ring': 'pulse-ring 1.5s ease-out infinite',
        'pulse-glow': 'pulse-glow 1.5s ease-in-out infinite',
        'scale-pulse': 'scale-pulse 1.5s ease-in-out infinite',
        'slide-down': 'slide-down 0.3s ease',
        'spring-in': 'spring-in 0.35s ease',
        'empty-pulse': 'empty-pulse 2.5s ease-in-out infinite',
        'gradient-shift': 'gradient-shift 6s ease-in-out infinite',
        shake: 'shake 0.4s ease',
        shimmer: 'shimmer 1.5s infinite',
        spin: 'spin 0.8s linear infinite',
      },
      keyframes: {
        drift: {
          '0%': { transform: 'translate(0, 0)', opacity: '0' },
          '20%': { opacity: '0.7' },
          '100%': { transform: 'translate(var(--dx, 40px), var(--dy, -60px))', opacity: '0' },
        },
        'wave-bar': {
          '0%, 100%': { transform: 'scaleY(0.25)', opacity: '0.5' },
          '50%': { transform: 'scaleY(1)', opacity: '1' },
        },
        'bubble-in': {
          from: { transform: 'scale(0.85)', opacity: '0' },
          to: { transform: 'scale(1)', opacity: '1' },
        },
        'border-travel': {
          '0%': { transform: 'translateY(-100%)', opacity: '0' },
          '20%': { opacity: '1' },
          '80%': { opacity: '1' },
          '100%': { transform: 'translateY(180%)', opacity: '0' },
        },
        'streaming-cursor': {
          '0%, 50%': { opacity: '1' },
          '51%, 100%': { opacity: '0' },
        },
        'typing-dot': {
          '0%, 60%, 100%': { transform: 'translateY(0)', opacity: '0.4' },
          '30%': { transform: 'translateY(-4px)', opacity: '1' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(0.8)', opacity: '0.6' },
          '100%': { transform: 'scale(2)', opacity: '0' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(244, 63, 94, 0.55)' },
          '50%': { boxShadow: '0 0 0 8px rgba(244, 63, 94, 0)' },
        },
        'scale-pulse': {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.15)' },
        },
        'slide-down': {
          from: { transform: 'translateY(-100%)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        'spring-in': {
          '0%': { transform: 'scale(0)', opacity: '0' },
          '60%': { transform: 'scale(1.12)', opacity: '1' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        'empty-pulse': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.7' },
          '50%': { transform: 'scale(1.06)', opacity: '1' },
        },
        'gradient-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '20%': { transform: 'translateX(-3px)' },
          '40%': { transform: 'translateX(3px)' },
          '60%': { transform: 'translateX(-2px)' },
          '80%': { transform: 'translateX(2px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200px 0' },
          '100%': { backgroundPosition: 'calc(200px + 100%) 0' },
        },
        spin: {
          to: { transform: 'rotate(360deg)' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
