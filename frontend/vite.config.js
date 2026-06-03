import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Spring Boot API Gateway (user auth, scheme history, CSC locations)
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      },
      // FastAPI AI Hub — voice conversation endpoints
      '/voice': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // FastAPI AI Hub — OCR / Jan-Sahayak Lens (NEW)
      '/ocr': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // FastAPI AI Hub — Yojna Sathi agent interview
      '/agent': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // FastAPI AI Hub — status tracker
      '/status': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // FastAPI AI Hub — apply guide
      '/apply': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // FastAPI AI Hub — Jan Sahayak helper network
      '/sahayak': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

