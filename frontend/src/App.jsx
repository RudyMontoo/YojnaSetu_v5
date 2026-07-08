import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { useScroll } from 'framer-motion'
import { LanguageProvider } from './lib/i18n'
import SplashScreen from './pages/SplashScreen'  // eager: it's the "/" landing, so it paints instantly
import './index.css'

// Route-based code splitting: each page is its own chunk, fetched only when
// its route is visited. On the low-end / poor-connection devices this app
// targets, that's the difference between downloading one screen's worth of
// JS on first load vs. the entire twelve-page app. SplashScreen stays eager
// so the very first paint needs no extra round-trip.
const SignInPage = lazy(() => import('./pages/SignInPage'))
const HomePage = lazy(() => import('./pages/HomePage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const StatusPage = lazy(() => import('./pages/StatusPage'))
const SchemesPage = lazy(() => import('./pages/SchemesPage'))
const SchemeDetailPage = lazy(() => import('./pages/SchemeDetailPage'))
const ScannerPage = lazy(() => import('./pages/ScannerPage'))
const CSCFinderPage = lazy(() => import('./pages/CSCFinderPage'))
const CscDashboardPage = lazy(() => import('./pages/CscDashboardPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const MythosPreview = lazy(() => import('./pages/preview/MythosPreview'))
const MandalaTower3D = lazy(() => import('./components/MandalaTower3D'))

// Full-page fixed 3D chakra — same look as Sathi, on every page including Home.
// Home: scroll-driven (progress = scrollYProgress).
// All other pages: continuous auto-flight (no progress prop).
function GlobalBackground3D() {
  const { pathname } = useLocation()
  const { scrollYProgress } = useScroll()
  const reduce = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce || pathname.startsWith('/preview')) return null
  const isHome = pathname === '/home'
  return (
    <div className="app-3d-bg">
      <Suspense fallback={null}>
        <MandalaTower3D
          height="100%"
          progress={isHome ? () => scrollYProgress.get() : undefined}
        />
      </Suspense>
    </div>
  )
}

export default function App() {
  return (
    <LanguageProvider>
    <BrowserRouter>
      <GlobalBackground3D />
      <Suspense fallback={null}>
        <Routes>
          <Route path="/" element={<SplashScreen />} />
          <Route path="/signin" element={<SignInPage />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/status" element={<StatusPage />} />
          <Route path="/schemes" element={<SchemesPage />} />
          <Route path="/schemes/:id" element={<SchemeDetailPage />} />
          <Route path="/scanner" element={<ScannerPage />} />
          <Route path="/csc-finder" element={<CSCFinderPage />} />
          <Route path="/csc-dashboard" element={<CscDashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/preview/mythos" element={<MythosPreview />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
    </LanguageProvider>
  )
}
