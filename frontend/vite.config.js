import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: proxy /api sang backend (cổng 8000 mặc định hoặc mock 8010 qua VITE_API_TARGET)
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173, proxy: { '/api': process.env.VITE_API_TARGET || 'http://localhost:8000' } },
})
