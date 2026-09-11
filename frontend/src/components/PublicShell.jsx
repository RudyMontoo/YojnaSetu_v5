import { Link, NavLink } from 'react-router-dom'
import { Menu, X, ArrowLeft } from 'lucide-react'
import { useState } from 'react'
import { useLang, LANGUAGES } from '../lib/i18n'
import '../pages/public/PublicPages.css'

/**
 * The whole product, not just the credit module.
 *
 * The public pages started life covering only SC concessional credit, which
 * made the landing page a dead end: Sathi, the full scheme catalogue, the
 * document scanner and the helper network were all still there and working,
 * just unreachable from anything a logged-out visitor could see.
 *
 * Everything here is reachable without an account. The pages that genuinely
 * need an identity (track an application, the helper portal) prompt for login
 * at the point of action instead of hiding.
 */
// "Check eligibility" and "Ask Sathi" used to be two separate links: the
// same conversational assistant under two names, one of them (/chat)
// opening the OLD app's chat screen — a completely different visual theme
// from these StartGo pages, and a confusing second front door into what is
// functionally the same feature. EligibilityPage (at /eligibility) IS Sathi
// now — one chat, one entry point, correctly labelled for what it does.
const NAV = [
    { to: '/credit-schemes', label: 'Credit schemes' },
    { to: '/eligibility', label: 'Ask Sathi' },
    { to: '/emi-calculator', label: 'EMI calculator' },
    { to: '/csc-finder', label: 'Get help' },
]

/**
 * Chrome for the StartGo pages: YojnaSarthi brand on the left, language
 * switcher on the right.
 *
 * Deliberately NOT the app's Navbar — that one carries the saffron/glass
 * treatment these pages opt out of. There is intentionally no Login button
 * here: sign-in lives in the app navbar, so the product has exactly one place
 * to log in rather than two that can disagree about your state.
 */
export function PublicHeader({ tr = (s) => s }) {
    const { lang, setLang } = useLang()
    const [menuOpen, setMenuOpen] = useState(false)

    return (
        <header className="gov-header">
            <div className="gov-container gov-header-inner">
                <Link to="/startgo" className="gov-brand">
                    <img src="/logo.png" alt="" />
                    <span>
                        <span className="gov-brand-name">Yojna<span>Sarthi</span></span>
                        <span className="gov-brand-sub">Jan Jan Ko Yojana Se Jodo</span>
                    </span>
                </Link>

                <div className="gov-header-actions">
                    <button
                        className="gov-btn gov-btn-ghost gov-btn-sm gov-menu-toggle"
                        onClick={() => setMenuOpen((o) => !o)}
                        aria-label="Menu"
                        aria-expanded={menuOpen}
                    >
                        {menuOpen ? <X size={16} /> : <Menu size={16} />}
                    </button>

                    <select
                        className="gov-lang-select"
                        value={lang}
                        onChange={(e) => setLang(e.target.value)}
                        aria-label="Language"
                    >
                        {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                    </select>

                    {/* StartGo is reached from the app navbar, so it needs a way
                        back to it — these pages hide that navbar entirely. */}
                    <Link to="/home" className="gov-btn gov-btn-ghost gov-btn-sm">
                        <ArrowLeft size={15} /> {tr('Back to app')}
                    </Link>
                </div>
            </div>

            <nav className={`gov-nav ${menuOpen ? 'open' : ''}`}>
                <div className="gov-container gov-nav-inner">
                    {NAV.map(({ to, label }) => (
                        <NavLink
                            key={to}
                            to={to}
                            onClick={() => setMenuOpen(false)}
                            className={({ isActive }) => `gov-nav-link ${isActive ? 'active' : ''}`}
                        >
                            {tr(label)}
                        </NavLink>
                    ))}
                </div>
            </nav>
        </header>
    )
}

/** Trust/ownership cues. The encryption claim is true — see FieldEncryptionService. */
export function PublicFooter({ tr = (s) => s }) {
    return (
        <footer className="gov-footer">
            <div className="gov-container">
                <p><strong>YojnaSarthi</strong> — {tr('an initiative for financial inclusion of SC beneficiaries.')}</p>
                <p>{tr('Your data is encrypted and stored securely, and is used only to check scheme eligibility and process your application.')}</p>
                <p>{tr('Scheme figures are sourced from NSFDC. Confirm exact terms with the lending branch before you rely on them.')}</p>
            </div>
        </footer>
    )
}

/** Page frame: opaque gov-styled surface + header + footer. */
export function PublicPage({ children, tr }) {
    return (
        <div className="gov">
            <PublicHeader tr={tr} />
            {children}
            <PublicFooter tr={tr} />
        </div>
    )
}
