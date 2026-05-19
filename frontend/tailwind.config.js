/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'ui': ['"Silkscreen"', 'cursive'],          // Чистый пиксель для кнопок и HUD
        'dialogue': ['"Share Tech Mono"', 'monospace'], // Терминальный кибер-шрифт для чтения
      }
    },
  },
  plugins: [],
}