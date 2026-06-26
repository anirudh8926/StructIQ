import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API calls to the FastAPI backend on :8000 so the frontend can
// fetch('/model') etc. without CORS juggling. In prod, FastAPI serves the built dist.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/upload': 'http://localhost:8000',
      '/check': 'http://localhost:8000',
      '/model': 'http://localhost:8000',
      '/baseline': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
