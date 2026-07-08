import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { registerSW } from 'virtual:pwa-register'

// PWA service worker — auto-updates in the background when a new build ships
// (Workbox skipWaiting + clientsClaim via registerType:'autoUpdate'). Guarded
// so a SW registration failure can never block the app from rendering.
try {
  registerSW({ immediate: true })
} catch {
  /* SW unsupported / blocked — app still works online, just no offline cache */
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
