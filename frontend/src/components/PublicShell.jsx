import { Link, useLocation, useNavigate } from 'react-router-dom'
import { LogIn, User } from 'lucide-react'
import { useLang, LANGUAGES } from '../lib/i18n'
import { getLocalUser } from '../lib/auth'
import '../pages/public/PublicPages.css'

/**
 * Chrome for the public (pre-login) pages: YojnaSarthi brand on the left,
 * language switcher + a Login affordance on the right.
 *
 * Deliberately NOT the app's Navbar. That one assumes a signed-in citizen —
 * it links straight to /profile and /status and has no logged-out state — and
 * it carries the saffron/glass treatment these pages opt out of. A guest
 * needs exactly two things in the header: a way to change language, and a way
 * to sign in when they decide to act.
 *
 * The Login button passes the current location as `from`, so signing in
 * returns the citizen to the page they were reading rather than dumping them
 * on /home (see SignInPage.finishLogin).
 */
export function PublicHeader() {
    const { lang, setLang } = useLang()
    const location = useLocation()
    const navigate = useNavigate()
    const user = getLocalUser()

    return (
        <header className="gov-header">
            <div className="gov-container gov-header-inner">
                <Link to="/" className="gov-brand">
                    <img src="/logo.png" alt="" />
                    <span>
                        <span className="gov-brand-name">Yojna<span>Sarthi</span></span>
                        <span className="gov-brand-sub">Jan Jan Ko Yojana Se Jodo</span>
                    </span>
                </Link>

                <div className="gov-header-actions">
                    <select
                        className="gov-lang-select"
                        value={lang}
                        onChange={(e) => setLang(e.target.value)}
                        aria-label="Language"
                    >
                        {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                    </select>

                    {user ? (
                        <button className="gov-btn gov-btn-ghost gov-btn-sm" onClick={() => navigate('/home')}>
                            <User size={15} /> My account
                        </button>
                    ) : (
                        <button
                            className="gov-btn gov-btn-primary gov-btn-sm"
                            onClick={() => navigate('/signin', { state: { from: location.pathname + location.search } })}
                        >
                            <LogIn size={15} /> Login
                        </button>
                    )}
                </div>
            </div>
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
            <PublicHeader />
            {children}
            <PublicFooter tr={tr} />
        </div>
    )
}
