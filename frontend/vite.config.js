import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    // Installable PWA + offline support. Target users often have patchy
    // connectivity, so the app shell must load offline and already-seen
    // scheme data must survive a dropped connection. Workbox precaches the
    // built shell (auto-updates on new deploys) and runtime-caches the
    // read-only scheme APIs. Auth/chat/voice are deliberately NOT cached —
    // stale auth or a cached AI reply would be worse than an honest offline
    // error.
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['logo.png', 'logo.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'Yojna Setu — Sarkari Yojana Sathi',
        short_name: 'Yojna Setu',
        description: 'Discover and apply for Indian government welfare schemes in 22 languages — text, voice, and document scan.',
        lang: 'en',
        theme_color: '#0d0e1c',
        background_color: '#0d0e1c',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/home',
        scope: '/',
        icons: [
          { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: '/pwa-maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Precache the app shell (JS/CSS/HTML/icons). SPA fallback so any
        // client-side route resolves to index.html when offline.
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallback: '/index.html',
        // The three-fiber chunk is ~890KB — raise the precache size limit.
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        runtimeCaching: [
          {
            // Read-only scheme catalogue / trending / recent: serve from
            // network when online, fall back to the last cached copy offline.
            urlPattern: ({ url }) => url.pathname.startsWith('/api/v2/schemes'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'schemes-api',
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 7 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
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
      // FastAPI AI Hub — live Sarvam-Mayura translation (cached)
      '/translate': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

