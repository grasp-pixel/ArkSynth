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
        'ark-white': '#e8e8e8',
        'ark-gray': '#8a8a8a',
        'ark-orange': '#ff6600',
        'ark-orange-light': '#ff8c00',
        'ark-yellow': '#ffc107',
        // 블루 계열 (명일방주 스타일)
        'ark-cyan': '#54A2D8',
        'ark-cyan-dark': '#3A8BC4',
        'ark-cyan-light': '#7AB8E2',
        'ark-blue': '#54A2D8',
        'ark-blue-dark': '#2E6B9E',
        // 하위 호환성
        'ark-accent': '#3d3d3d',
        'ark-highlight': '#ff6600',
      },
      fontFamily: {
        'ark': ['Rajdhani', 'Noto Sans KR', 'sans-serif'],
      },
      boxShadow: {
        'ark': '0 0 10px rgba(255, 102, 0, 0.3)',
        'ark-glow': '0 0 20px rgba(255, 102, 0, 0.5)',
        'ark-cyan': '0 0 10px rgba(84, 162, 216, 0.3)',
        'ark-cyan-glow': '0 0 20px rgba(84, 162, 216, 0.5)',
      },
    },
  },
  plugins: [],
}
