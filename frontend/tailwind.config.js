export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        blush: {
          50: '#fff1f4',
          100: '#ffe4ea',
          200: '#fecdd8',
          300: '#fda4ba',
          400: '#fb7185',
          500: '#f43f5e'
        },
        sand: {
          50: '#faf7f2',
          100: '#f5efe6',
          200: '#e9dcc9'
        }
      },
      boxShadow: {
        soft: '0 10px 30px rgba(17, 24, 39, 0.08)'
      },
      borderRadius: {
        xl: '1.25rem'
      }
    }
  },
  plugins: []
}
