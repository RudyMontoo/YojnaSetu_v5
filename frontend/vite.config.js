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
      // FastAPI — v5.0 LangGraph orchestrator (12-agent chat)
      '/orchestrator': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // FastAPI — v5.0 chat WebSocket (token streaming). ws:true is required
      // or Vite silently drops the Upgrade handshake.
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      // FastAPI — v5.0 agent endpoints (financial plan, PPO verify, grievance)
      '/agents': {
        target: 'http://localhost:8000',
        changeOrigin: true,
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
      // FastAPI AI Hub — status tracker API (narrowed: bare /status is the SPA route)
      '/status/check': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // FastAPI AI Hub — apply guide
      '/apply': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

