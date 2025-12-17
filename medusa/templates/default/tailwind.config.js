/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './site/**/*.{md,jinja}',
    './assets/**/*.js',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
