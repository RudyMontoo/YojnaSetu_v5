import { NavLink } from 'react-router-dom'
import { Home, MessageCircle, FileText, Radio, User, Camera, Globe, Sun, Moon } from 'lucide-react'
import { useLang, LANGUAGES } from '../lib/i18n'
import { useState, useEffect } from 'react'
import { getTheme, setTheme } from '../lib/theme'
import './Navbar.css'

const NAV_ITEMS = [
    { to: '/home', key: 'nav.home', Icon: Home },
    { to: '/chat', key: 'nav.sathi', Icon: MessageCircle },
    { to: '/schemes', key: 'nav.schemes', Icon: FileText },
    { to: '/status', key: 'nav.status', Icon: Radio },
    { to: '/scanner', key: 'nav.lens', Icon: Camera },
    { to: '/profile', key: 'nav.profile', Icon: User },
]

export function ThemeToggle({ compact = false }) {
    const [theme, setThemeState] = useState(getTheme())

    useEffect(() => {
        setTheme(theme)
    }, [theme])

    const toggle = () => setThemeState((t) => (t === 'dark' ? 'light' : 'dark'))

    return (
        <button
            type="button"
            className={`theme-toggle ${compact ? 'compact' : ''}`}
            onClick={toggle}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        </button>
    )
}

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
                    <img src="/logo.png" alt="Yojna Sarthi" className="logo-img" />
                </div>
            </NavLink>
            <div className="navbar-links">
                {NAV_ITEMS.map(({ to, key }) => (
                    <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                        {t(key)}
                    </NavLink>
                ))}
                <ThemeToggle />
                <LanguageSwitcher />
            </div>
            {/* .navbar-links hides at mobile widths — this is its mobile
                replacement, living inside the SAME already-reliably-fixed
                navbar bar rather than as its own independent fixed-position
                element. The standalone .mobile-lang-fab it replaces was
                mis-positioning itself on some mobile contexts (a second
                independent `position: fixed` layer is inherently more
                fragile than reusing the one that's already proven to work
                on every screen). */}
            <div className="navbar-mobile-controls">
                <ThemeToggle compact />
                <LanguageSwitcher compact />
            </div>
        </nav>
    )
}

/* Bottom tab bar for mobile */
export function BottomNav() {
    const { t } = useLang()
    return (
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
    )
}
