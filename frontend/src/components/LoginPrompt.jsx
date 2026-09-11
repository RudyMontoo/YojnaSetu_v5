import { useLocation, useNavigate } from 'react-router-dom'
import { LogIn, X } from 'lucide-react'
import '../pages/public/PublicPages.css'

/**
 * The "log in only when you act" prompt.
 *
 * Browsing, eligibility, and the EMI calculator are all open. This appears
 * only at the moment a citizen tries to do something that is genuinely tied
 * to an identity — apply, save, track, download a personalised document.
 *
 * Phrased as an invitation ("Login to apply for this scheme"), never as a
 * wall ("You must register to continue"): the citizen has already invested
 * effort by this point, and the message should read as the next step rather
 * than a refusal.
 *
 * Carries the current location through as `from`, so SignInPage can return
 * them to exactly where they were instead of dropping them on /home.
 */
export default function LoginPrompt({ open, onClose, action = 'continue', children }) {
    const navigate = useNavigate()
    const location = useLocation()
    if (!open) return null

    const goSignIn = () => {
        navigate('/signin', { state: { from: location.pathname + location.search } })
    }

    return (
        <div
            className="gov"
            style={{
                position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(12,16,23,.55)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
                minHeight: 'auto',
            }}
            onClick={onClose}
            role="presentation"
        >
            <div
                className="gov-card"
                style={{ maxWidth: 420, width: '100%', position: 'relative' }}
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
            >
                <button
                    onClick={onClose}
                    aria-label="Close"
                    style={{ position: 'absolute', top: 12, right: 12, background: 'none', border: 0, cursor: 'pointer', color: 'var(--gov-muted)' }}
                >
                    <X size={18} />
                </button>

                <h3 style={{ marginBottom: 8, paddingRight: 24 }}>Login to {action}</h3>
                <p style={{ fontSize: 14, lineHeight: 1.6, marginBottom: 6 }}>
                    {children || 'Create an account or sign in to continue. It only takes a minute — we just need your mobile number.'}
                </p>
                <p className="gov-hint" style={{ marginBottom: 18 }}>
                    Anything you have already filled in will be kept and carried over after you sign in.
                </p>

                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <button className="gov-btn gov-btn-primary" onClick={goSignIn} style={{ flex: '1 1 160px' }}>
                        <LogIn size={17} /> Login / Register
                    </button>
                    <button className="gov-btn gov-btn-ghost" onClick={onClose} style={{ flex: '0 1 auto' }}>
                        Keep browsing
                    </button>
                </div>
            </div>
        </div>
    )
}
