import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { FlaskConical, ShieldCheck, ArrowRight, Loader2 } from 'lucide-react'
import { gateway } from '../lib/api'
import './public/PublicPages.css'

/**
 * A STAND-IN for DigiLocker's own consent screen, shown only when the gateway
 * runs with `app.demo.simulate-integrations=true`.
 *
 * Why it exists: DigiLocker Partner API credentials require a business
 * registration that this project does not have, so the real authorize URL
 * cannot be reached. Without this screen the simulated flow dead-ends at a
 * link nobody can open, and the DigiLocker journey can't be shown at all.
 *
 * The one hard rule: this must never be mistakable for the real thing. It says
 * "simulated" in the heading, the banner and the button, it is not styled to
 * imitate DigiLocker's branding, and the link it completes is stored with
 * `simulated: true` so nothing downstream reads it as a genuine verification.
 *
 * The citizen's browser arrives here with the single-use `state` nonce that
 * DigiLockerService generated; "Allow" hands it back to the real callback,
 * which is the same code path a live DigiLocker redirect would take.
 */
export default function DigiLockerDemoPage() {
    const [params] = useSearchParams()
    const navigate = useNavigate()
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')
    const state = params.get('state') || ''

    const allow = async () => {
        setBusy(true)
        setError('')
        try {
            // `code` is ignored by the simulated path — there is no token
            // exchange because there is no real account on the other end.
            await gateway.digilockerCallback(state, 'SIMULATED-AUTH-CODE')
            navigate('/profile', { replace: true })
        } catch (e) {
            setError(e.message)
            setBusy(false)
        }
    }

    return (
        <div className="gov">
            <div className="gov-container" style={{ maxWidth: 560, padding: '48px 20px' }}>
                <div className="gov-card">
                    <p className="gov-notice gov-notice-warn">
                        <FlaskConical size={14} /> This is a <strong>simulated</strong> DigiLocker screen, not
                        DigiLocker. It exists so the connection flow can be demonstrated without DigiLocker
                        Partner credentials. Nothing here reaches a real DigiLocker account.
                    </p>

                    <h2 style={{ marginTop: 18 }}>Simulated DigiLocker consent</h2>
                    <p className="gov-scheme-desc">
                        In the real flow, DigiLocker would ask you to sign in and approve this request. Yojna
                        Sarthi is asking for read access to your issued documents — your Aadhaar, caste
                        certificate, income certificate and marksheets — so you do not have to photograph and
                        upload them yourself.
                    </p>

                    {!state && (
                        <div className="gov-notice gov-notice-error">
                            This link is missing its security token. Start again from your profile.
                        </div>
                    )}
                    {error && <div className="gov-notice gov-notice-error">{error}</div>}

                    <div className="gov-hero-actions" style={{ marginTop: 18 }}>
                        <button className="gov-btn gov-btn-primary" onClick={allow} disabled={busy || !state}>
                            {busy ? <Loader2 size={16} className="spin" /> : <ShieldCheck size={16} />}
                            {busy ? 'Connecting…' : 'Allow (simulated)'}
                        </button>
                        <button className="gov-btn gov-btn-secondary" onClick={() => navigate('/profile')} disabled={busy}>
                            Cancel <ArrowRight size={15} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
