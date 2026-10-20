import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Backend target is overridable so an isolated stack (alternate port) can be
// driven without disturbing the canonical dev server on 5050.
const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:5050'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: backend,
        changeOrigin: true,
      },
    },
  },
})
