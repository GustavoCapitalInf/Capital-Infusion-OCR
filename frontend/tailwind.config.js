/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      // ── Typography (Calistoga + Inter + JetBrains Mono — fintech SaaS stack)
      fontFamily: {
        display: ['Calistoga', 'Georgia', 'serif'],   // hero/display headings
        sans:    ['Inter', 'system-ui', 'sans-serif'], // body, UI labels
        mono:    ['JetBrains Mono', 'Menlo', 'monospace'], // ALL numeric values
      },

      // ── Color tokens (Financial Dashboard palette from ui-ux-pro-max)
      // Semantic tokens are wired to CSS variables so dark mode switches automatically.
      colors: {
        // Sidebar (OLED dark — same in both modes)
        sidebar: {
          DEFAULT: '#080E1C',
          hover:   '#0D1528',
          border:  'rgba(255,255,255,0.06)',
          muted:   '#94A3B8',
          dim:     '#64748B',
        },
        // Surfaces — driven by CSS vars (see index.css :root / html.dark)
        surface: 'rgb(var(--surface) / <alpha-value>)',
        card: {
          DEFAULT: 'rgb(var(--card) / <alpha-value>)',
          hover:   'rgb(var(--card-hover) / <alpha-value>)',
        },
        // Fintech semantic palette (kept constant — work on both backgrounds)
        accent:  { DEFAULT: '#22C55E', dark: '#16A34A', light: '#F0FDF4', border: '#BBF7D0' },
        primary: { DEFAULT: '#2563EB', dark: '#1D4ED8', light: '#EFF6FF', border: '#BFDBFE' },
        danger:  { DEFAULT: '#EF4444', light: '#FEF2F2', border: '#FECACA' },
        warning: { DEFAULT: '#F59E0B', light: '#FFFBEB', border: '#FDE68A' },
        purple:  { DEFAULT: '#7C3AED', light: '#F5F3FF', border: '#DDD6FE' },
        // Legacy aliases (keep existing components working)
        blue:    { DEFAULT: '#2563EB', dark: '#1D4ED8', light: '#EFF6FF', border: '#BFDBFE',
                   50:'#EFF6FF', 100:'#DBEAFE', 200:'#BFDBFE', 600:'#2563EB', 700:'#1D4ED8' },
        green:   { DEFAULT: '#22C55E', light: '#F0FDF4', border: '#BBF7D0', 600:'#16A34A', 700:'#15803D' },
        red:     { DEFAULT: '#EF4444', light: '#FEF2F2', border: '#FECACA', 600:'#DC2626' },
        amber:   { DEFAULT: '#F59E0B', light: '#FFFBEB', border: '#FDE68A', 600:'#D97706' },
        // Text scale — driven by CSS vars (auto-flips in dark mode)
        text: {
          primary:   'rgb(var(--text-primary) / <alpha-value>)',
          secondary: 'rgb(var(--text-secondary) / <alpha-value>)',
          muted:     'rgb(var(--text-muted) / <alpha-value>)',
          dim:       'rgb(var(--text-dim) / <alpha-value>)',
        },
        border: {
          DEFAULT: 'rgb(var(--border) / <alpha-value>)',
          light:   'rgb(var(--border-light) / <alpha-value>)',
        },
      },

      // ── Elevation scale
      boxShadow: {
        xs:     '0 1px 2px rgba(0,0,0,0.04)',
        sm:     '0 1px 3px rgba(0,0,0,0.06), 0 1px 8px rgba(0,0,0,0.04)',
        md:     '0 4px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)',
        lg:     '0 8px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.06)',
        'ring-primary': '0 0 0 3px rgba(37,99,235,0.15)',
        'ring-accent':  '0 0 0 3px rgba(34,197,94,0.20)',
        glow:   '0 4px 20px rgba(37,99,235,0.20)',
      },
      borderRadius: { '2xl':'16px', '3xl':'20px', '4xl':'24px' },

      // ── Motion tokens (150–300ms per ux-guidelines)
      transitionDuration: { fast: '150ms', base: '200ms', slow: '300ms' },
      transitionTimingFunction: {
        'ease-out-expo': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },

      // ── Animations
      animation: {
        'fade-in':    'fadeIn 250ms ease-out',
        'slide-up':   'slideUp 300ms cubic-bezier(0.16,1,0.3,1)',
        'slide-down': 'slideDown 250ms cubic-bezier(0.16,1,0.3,1)',
        'pulse-dot':  'pulseDot 2s ease-in-out infinite',
        shimmer:      'shimmer 1.6s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:    { from:{ opacity:0 },                         to:{ opacity:1 } },
        slideUp:   { from:{ opacity:0, transform:'translateY(10px)' }, to:{ opacity:1, transform:'translateY(0)' } },
        slideDown: { from:{ opacity:0, transform:'translateY(-6px)' }, to:{ opacity:1, transform:'translateY(0)' } },
        pulseDot:  { '0%,100%':{ opacity:1 }, '50%':{ opacity:0.4 } },
        shimmer:   { '0%':{ backgroundPosition:'-200% 0' }, '100%':{ backgroundPosition:'200% 0' } },
      },

      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'dot-grid': 'radial-gradient(circle, #E2E8F0 1px, transparent 1px)',
      },
      backgroundSize: { 'dot-20': '20px 20px' },
    },
  },
  plugins: [],
}
