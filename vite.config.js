import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The UI calls /api/...; Vite forwards it to FastAPI (API_URL, default port 8000), so no CORS setup is needed.
const proxy = { '/api': { target: process.env.API_URL ?? 'http://127.0.0.1:8000', rewrite: (path) => path.replace(/^\/api/, '') } }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy }, // `npm run preview` serves the production build the same way
})
