/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },
      colors: {
        surface: {
          0: '#080b10',
          1: '#0d1117',
          2: '#131920',
          3: '#1a2332',
          4: '#1f2b3a',
        },
        accent: {
          green: '#00d4a0',
          red: '#ff4d6a',
          blue: '#3b9eff',
          yellow: '#f5c518',
          purple: '#a78bfa',
        },
      },
    },
  },
  plugins: [],
}
