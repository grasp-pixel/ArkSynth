/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Rhodes Island 테마
        'ark-black': '#0d0d0d',
        'ark-dark': '#1a1a1a',
        'ark-panel': '#262626',
        'ark-border': '#3d3d3d',
        'ark-orange': '#ff6600',
        'ark-yellow': '#ffc107',
        'ark-white': '#e8e8e8',
        'ark-gray': '#8a8a8a',
        // 하위 호환성
        'ark-blue': '#1a1a1a',
        'ark-accent': '#3d3d3d',
        'ark-highlight': '#ff6600',
      },
      fontFamily: {
        'ark': ['Rajdhani', 'Noto Sans KR', 'sans-serif'],
      },
      boxShadow: {
        'ark': '0 0 10px rgba(255, 102, 0, 0.3)',
        'ark-glow': '0 0 20px rgba(255, 102, 0, 0.5)',
      },
    },
  },
  plugins: [],
}
