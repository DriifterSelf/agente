/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: '#0B0F17',
        surface: '#131926',
        surfaceHover: '#1B2436',
        border: '#1F293D',
        accent: '#3B82F6',
        accentHover: '#2563EB',
        textMain: '#F1F5F9',
        textMuted: '#94A3B8'
      }
    },
  },
  plugins: [],
}
