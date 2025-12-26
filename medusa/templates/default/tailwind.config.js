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
    require('@tailwindcss/forms'),
    require('@tailwindcss/aspect-ratio'),
    require('@tailwindcss/container-queries'),
  ],
}
