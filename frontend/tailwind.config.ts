import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
    './node_modules/@tremor/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        forest: {
          50: '#f0f7f4',
          100: '#dceee6',
          200: '#b8dece',
          300: '#8ec9ae',
          400: '#5eaf88',
          500: '#3a9469',
          600: '#2d7855',
          700: '#235f44',
          800: '#1a4733',
          900: '#113025',
          950: '#091a14',
        },
        lime: {
          100: '#f7fee7',
          200: '#ecfccb',
          300: '#d9f99d',
          400: '#bef264',
          500: '#a3e635',
        },
        tremor: {
          brand: {
            faint: '#eff6ff',
            muted: '#bfdbfe',
            subtle: '#60a5fa',
            DEFAULT: '#3b82f6',
            emphasis: '#1d4ed8',
            inverted: '#ffffff',
          },
          background: {
            muted: '#f9fafb',
            subtle: '#f3f4f6',
            DEFAULT: '#ffffff',
            emphasis: '#374151',
          },
          border: { DEFAULT: '#e5e7eb' },
          ring: { DEFAULT: '#e5e7eb' },
          content: {
            subtle: '#9ca3af',
            DEFAULT: '#6b7280',
            emphasis: '#374151',
            strong: '#111827',
            inverted: '#ffffff',
          },
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'ui-sans-serif', 'system-ui'],
        serif: ['var(--font-instrument-serif)', 'ui-serif', 'Georgia'],
      },
    },
  },
  plugins: [],
}

export default config
