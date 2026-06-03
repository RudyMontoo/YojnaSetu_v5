import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import SplashScreen from './pages/SplashScreen'
import SignInPage from './pages/SignInPage'
import OnboardingPage from './pages/OnboardingPage'
import HomePage from './pages/HomePage'
import ChatPage from './pages/ChatPage'
import StatusPage from './pages/StatusPage'
import SchemesPage from './pages/SchemesPage'
import SchemeDetailPage from './pages/SchemeDetailPage'
import ScannerPage from './pages/ScannerPage'
import HelperFinderPage from './pages/HelperFinderPage'
import HelperRegistrationPage from './pages/HelperRegistrationPage'
import HelperLoginPage from './pages/HelperLoginPage'
import HelperDashboardPage from './pages/HelperDashboardPage'
import CSCFinderPage from './pages/CSCFinderPage'
import ProfilePage from './pages/ProfilePage'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
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
        <Route path="/helpers" element={<HelperFinderPage />} />
        <Route path="/register-helper" element={<HelperRegistrationPage />} />
        <Route path="/helper-login" element={<HelperLoginPage />} />
        <Route path="/helper-dashboard" element={<HelperDashboardPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
