import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { useScroll } from 'framer-motion'
import { LanguageProvider } from './lib/i18n'
import ErrorBoundary from './components/ErrorBoundary'
import LandingPage from './pages/public/LandingPage'  // eager: it's the "/" landing, so it paints instantly
import './index.css'

// lazy() that survives a stale PWA deploy: if a page's chunk 404s because the
// cached app references an old hash, reload ONCE to fetch the fresh chunks
// instead of throwing into a black screen. (The ErrorBoundary is the backstop
// if the reload guard is already spent.)
const lazyWithReload = (factory) => lazy(() =>
  factory().catch((err) => {
    if (!sessionStorage.getItem('chunk-reloaded')) {
      sessionStorage.setItem('chunk-reloaded', '1')
      window.location.reload()
      return new Promise(() => {})  // hang until the reload takes over
    }
    throw err
  })
)

// Route-based code splitting: each page is its own chunk, fetched only when
// its route is visited. On the low-end / poor-connection devices this app
// targets, that's the difference between downloading one screen's worth of
// JS on first load vs. the entire twelve-page app. LandingPage stays eager
// so the very first paint needs no extra round-trip.
const SplashScreen = lazyWithReload(() => import('./pages/SplashScreen'))
const SignInPage = lazyWithReload(() => import('./pages/SignInPage'))
// Public, pre-login pages (PS 26092). Browsing, eligibility and the EMI
// calculator are all open — see PublicPages.css for why these carry their own
// plain government-portal styling rather than the app's themed look.
const CreditSchemeListPage = lazyWithReload(() => import('./pages/public/CreditSchemeListPage'))
const CreditSchemeDetailPage = lazyWithReload(() => import('./pages/public/CreditSchemeDetailPage'))
const EligibilityPage = lazyWithReload(() => import('./pages/public/EligibilityPage'))
const EmiCalculatorPage = lazyWithReload(() => import('./pages/public/EmiCalculatorPage'))
const PartnerLocatorPage = lazyWithReload(() => import('./pages/public/PartnerLocatorPage'))
const HomePage = lazyWithReload(() => import('./pages/HomePage'))
const ChatPage = lazyWithReload(() => import('./pages/ChatPage'))
const StatusPage = lazyWithReload(() => import('./pages/StatusPage'))
const SchemesPage = lazyWithReload(() => import('./pages/SchemesPage'))
const SchemeDetailPage = lazyWithReload(() => import('./pages/SchemeDetailPage'))
const ScannerPage = lazyWithReload(() => import('./pages/ScannerPage'))
const CSCFinderPage = lazyWithReload(() => import('./pages/CSCFinderPage'))
const CscDashboardPage = lazyWithReload(() => import('./pages/CscDashboardPage'))
const ProfilePage = lazyWithReload(() => import('./pages/ProfilePage'))
const BecomeHelperPage = lazyWithReload(() => import('./pages/BecomeHelperPage'))
const HelperPortalPage = lazyWithReload(() => import('./pages/HelperPortalPage'))
const AdminPortalPage = lazyWithReload(() => import('./pages/AdminPortalPage'))
const MythosPreview = lazyWithReload(() => import('./pages/preview/MythosPreview'))
const ApplyPage = lazyWithReload(() => import('./pages/ApplyPage'))
const MandalaTower3D = lazy(() => import('./components/MandalaTower3D'))

// Full-page fixed 3D chakra — same look as Sathi, on every page including Home.
// Home: scroll-driven (progress = scrollYProgress).
// All other pages: continuous auto-flight (no progress prop).
// The public pages are deliberately plain — a government-service look, and
// light enough for a low-end phone on 3G. The WebGL chakra is neither, so
// they opt out of it the same way /preview already does.
const PUBLIC_PATHS = ['/credit-schemes', '/eligibility', '/emi-calculator', '/partner-locator']
const isPublicPath = (pathname) =>
  pathname === '/' || PUBLIC_PATHS.some((p) => pathname.startsWith(p))

function GlobalBackground3D() {
  const { pathname } = useLocation()
  const { scrollYProgress } = useScroll()
  const reduce = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce || pathname.startsWith('/preview') || isPublicPath(pathname)) return null
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
      <ErrorBoundary>
      <Suspense fallback={null}>
        <Routes>
          {/* Public, no login required — a citizen must be able to learn what
              they qualify for before creating an account. The splash screen
              used to sit here and bounce every visitor to /signin. */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/credit-schemes" element={<CreditSchemeListPage />} />
          <Route path="/credit-schemes/:id" element={<CreditSchemeDetailPage />} />
          <Route path="/eligibility" element={<EligibilityPage />} />
          <Route path="/emi-calculator" element={<EmiCalculatorPage />} />
          <Route path="/partner-locator" element={<PartnerLocatorPage />} />
          <Route path="/splash" element={<SplashScreen />} />

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
          <Route path="/become-helper" element={<BecomeHelperPage />} />
          <Route path="/helper" element={<HelperPortalPage />} />
          <Route path="/admin" element={<AdminPortalPage />} />
          <Route path="/preview/mythos" element={<MythosPreview />} />
          <Route path="/apply/:schemeId" element={<ApplyPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      </ErrorBoundary>
    </BrowserRouter>
    </LanguageProvider>
  )
}
