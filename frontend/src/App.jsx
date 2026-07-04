import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import SplashScreen from './pages/SplashScreen'
import SignInPage from './pages/SignInPage'
import OnboardingPage from './pages/OnboardingPage'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import StatusPage from './pages/StatusPage'
import SchemesPage from './pages/SchemesPage'
import SchemeDetailPage from './pages/SchemeDetailPage'
import ScannerPage from './pages/ScannerPage'
import CSCFinderPage from './pages/CSCFinderPage'
import CscDashboardPage from './pages/CscDashboardPage'
import ProfilePage from './pages/ProfilePage'
import { lazy, Suspense } from 'react'
import { useScroll } from 'framer-motion'
import { LanguageProvider } from './lib/i18n'
import './index.css'

const MythosPreview = lazy(() => import('./pages/preview/MythosPreview'))
const MandalaTower3D = lazy(() => import('./components/MandalaTower3D'))

// Full-page fixed 3D chakra — same look as Sathi, now on EVERY page including Home.
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
      <Routes>
        <Route path="/" element={<SplashScreen />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/home" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/schemes" element={<SchemesPage />} />
        <Route path="/schemes/:id" element={<SchemeDetailPage />} />
        <Route path="/scanner" element={<ScannerPage />} />
        <Route path="/csc-finder" element={<CSCFinderPage />} />
        <Route path="/csc-dashboard" element={<CscDashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/preview/mythos" element={<Suspense fallback={null}><MythosPreview /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
    </LanguageProvider>
  )
}
