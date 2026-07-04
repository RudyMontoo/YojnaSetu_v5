import { NavLink } from 'react-router-dom'
import { Home, MessageCircle, FileText, Radio, User, Camera, Globe } from 'lucide-react'
import { useLang, LANGUAGES } from '../lib/i18n'
import './Navbar.css'

const NAV_ITEMS = [
    { to: '/home', key: 'nav.home', Icon: Home },
    { to: '/chat', key: 'nav.sathi', Icon: MessageCircle },
    { to: '/schemes', key: 'nav.schemes', Icon: FileText },
    { to: '/status', key: 'nav.status', Icon: Radio },
    { to: '/scanner', key: 'nav.lens', Icon: Camera },
    { to: '/profile', key: 'nav.profile', Icon: User },
]

export function LanguageSwitcher({ compact = false }) {
    const { lang, setLang } = useLang()
    return (
        <label className={`lang-switcher ${compact ? 'compact' : ''}`}>
            <Globe size={14} />
            <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
                {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
            </select>
        </label>
    )
}

/* Animated SVG Logo removed - User requested original logo.png */

/* Top navigation for desktop */
export function Navbar() {
    const { t } = useLang()
    return (
        <nav className="navbar">
            <NavLink to="/home" className="navbar-logo">
                <div className="logo-img-circle">
                    <img src="/logo.png" alt="Yojna Setu" className="logo-img" />
                </div>
            </NavLink>
            <div className="navbar-links">
                {NAV_ITEMS.map(({ to, key }) => (
                    <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        {t(key)}
                    </NavLink>
                ))}
                <LanguageSwitcher />
            </div>
        </nav>
    )
}

/* Bottom tab bar for mobile */
export function BottomNav() {
    const { t } = useLang()
    return (
        <>
        <div className="mobile-lang-fab"><LanguageSwitcher compact /></div>
        <nav className="bottom-nav">
            {NAV_ITEMS.map((item) => {
                const NavIcon = item.Icon
                return (
                    <NavLink key={item.to} to={item.to} className={({ isActive }) => `bottom-nav-item ${isActive ? 'active' : ''}`}>
                        <NavIcon size={20} />
                        <span>{t(item.key)}</span>
                    </NavLink>
                )
            })}
        </nav>
        </>
    )
}
