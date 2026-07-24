import { useState, useEffect } from 'react'
import { Mail, KeyRound, LogIn, ShieldCheck, CheckCircle2, XCircle, RefreshCw, Copy, BadgeCheck } from 'lucide-react'
import { gateway } from '../lib/api'
import './SignInPage.css'

// Separate admin portal — unlisted from the citizen app. The admin logs in with
// their (ADMIN-role) email OTP, reviews helper applications, and Confirms them —
// which mints + emails the helper's credentials.
export default function AdminPortalPage() {
    const [mode, setMode] = useState('loading')  // loading | login | dashboard | notadmin
    const [step, setStep] = useState('email')     // email | otp
    const [email, setEmail] = useState('')
    const [otp, setOtp] = useState('')
    const [apps, setApps] = useState([])
    const [issued, setIssued] = useState({})       // appId -> { helperId, tempPassword, emailedTo }
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)

    useEffect(() => { load().then(ok => setMode(ok ? 'dashboard' : 'login')) }, [])

    const load = async () => {
        try { const r = await gateway.helperApplications(); setApps(r.applications || []); return true }
        catch (e) { if (e.status === 403) setMode('notadmin'); return false }
    }

    const sendOtp = async (e) => {
        e.preventDefault(); setError(''); setBusy(true)
        try { await gateway.sendOtp({ email: email.trim() }); setStep('otp') }
        catch (err) { setError(err.message || 'Could not send OTP') }
        finally { setBusy(false) }
    }
    const verifyOtp = async (e) => {
        e.preventDefault(); setError(''); setBusy(true)
        try {
            await gateway.verifyOtp({ email: email.trim() }, otp.trim())
            const ok = await load()
            setMode(ok ? 'dashboard' : 'notadmin')
        } catch (err) { setError(err.message || 'Incorrect OTP') }
        finally { setBusy(false) }
    }

    const approve = async (id) => {
        try { const r = await gateway.approveHelper(id); setIssued(s => ({ ...s, [id]: r })) } catch (e) { setError(e.message) }
        finally { load() }
    }
    const reject = async (id) => { try { await gateway.rejectHelper(id) } finally { load() } }

    // ── login ──
    if (mode === 'login' || mode === 'loading') {
        return (
            <div className="signin-wrapper">
                <div className="signin-bg-glow" />
                <div className="signin-card glass-card">
                    <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>Admin<span className="text-saffron"> Console</span></h1>
                    <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 18 }}>Restricted — admin login required.</p>
                    {error && <p className="signin-error">{error}</p>}
                    {step === 'email' ? (
                        <form onSubmit={sendOtp} className="signin-form">
                            <p className="signin-label">Admin email</p>
                            <div className="signin-input-row">
                                <span className="signin-prefix"><Mail size={15} /></span>
                                <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@example.com" className="input-glass signin-input" autoFocus required />
                            </div>
                            <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || !email.trim()}>
                                {busy ? <span className="btn-spinner" /> : <>Send OTP</>}
                            </button>
                        </form>
                    ) : (
                        <form onSubmit={verifyOtp} className="signin-form">
                            <p className="signin-label">OTP sent to {email}</p>
                            <div className="signin-input-row">
                                <span className="signin-prefix"><KeyRound size={15} /></span>
                                <input inputMode="numeric" maxLength={6} value={otp} onChange={e => setOtp(e.target.value)} placeholder="••••••" className="input-glass signin-input" style={{ letterSpacing: 8, fontWeight: 700 }} autoFocus required />
                            </div>
                            <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || otp.trim().length !== 6}>
                                {busy ? <span className="btn-spinner" /> : <><LogIn size={16} /> Verify & Enter</>}
                            </button>
                        </form>
                    )}
                </div>
            </div>
        )
    }

    if (mode === 'notadmin') {
        return (
            <div className="signin-wrapper">
                <div className="signin-card glass-card" style={{ textAlign: 'center' }}>
                    <XCircle size={40} className="text-saffron" />
                    <h1 className="signin-brand font-display">Not an admin account</h1>
                    <p className="signin-sub">This console is restricted to administrators.</p>
                </div>
            </div>
        )
    }

    // ── dashboard ──
    return (
        <div className="page-wrapper">
            <header className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: 12, margin: 16, padding: '12px 16px' }}>
                <ShieldCheck size={22} className="text-saffron" />
                <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontWeight: 700 }}>Admin Console</p>
                    <p className="text-muted" style={{ margin: 0, fontSize: 12 }}>Helper applications</p>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCw size={14} /> Refresh</button>
            </header>
            <main className="page-content" style={{ paddingTop: 0 }}>
                <h1 style={{ fontSize: 20, marginBottom: 12 }}>Pending Applications{apps.length > 0 ? ` (${apps.length})` : ''}</h1>
                {error && <p className="signin-error">{error}</p>}
                {apps.length === 0 ? (
                    <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}><p className="text-muted">No pending applications.</p></div>
                ) : apps.map(a => (
                    <div key={a.id} className="glass-card" style={{ padding: 16, marginBottom: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                                <p style={{ margin: 0, fontWeight: 700, fontSize: 16 }}>{a.fullName}</p>
                                <a href={`tel:${a.phone}`} className="text-muted" style={{ fontSize: 13 }}>{a.phone}</a>
                            </div>
                            {a.aadhaarVerified
                                ? <span className="badge badge-green"><BadgeCheck size={12} /> Aadhaar verified</span>
                                : <span className="badge badge-muted">Aadhaar checksum failed</span>}
                        </div>
                        <table style={{ width: '100%', fontSize: 13, marginTop: 10 }}>
                            <tbody>
                                <tr><td className="text-muted" style={{ padding: '2px 8px 2px 0' }}>Aadhaar</td><td>{a.aadhaarMasked}</td></tr>
                                <tr><td className="text-muted" style={{ padding: '2px 8px 2px 0' }}>PAN</td><td>{a.pan}</td></tr>
                                <tr><td className="text-muted" style={{ padding: '2px 8px 2px 0' }}>Work proof</td><td>{a.workProofType}{a.workProofDetail ? ` — ${a.workProofDetail}` : ''}</td></tr>
                            </tbody>
                        </table>

                        {issued[a.id] ? (
                            <div className="glass-card glass-card-glow" style={{ padding: 12, marginTop: 12 }}>
                                <p style={{ margin: 0, fontWeight: 600 }}><CheckCircle2 size={14} className="text-saffron" /> Helper created</p>
                                <p style={{ margin: '6px 0', fontSize: 13 }}>ID: <b>{issued[a.id].helperId}</b> · Password: <b>{issued[a.id].tempPassword}</b></p>
                                <p className="text-muted" style={{ fontSize: 12, margin: 0 }}>
                                    {issued[a.id].emailedTo ? `Emailed to ${issued[a.id].emailedTo}` : 'No email on file — share these credentials with the helper.'}
                                </p>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                                <button className="btn btn-primary btn-aarti btn-sm" onClick={() => approve(a.id)}><CheckCircle2 size={14} /> Confirm & Issue Login</button>
                                <button className="btn btn-ghost btn-sm" onClick={() => reject(a.id)}><XCircle size={14} /> Reject</button>
                            </div>
                        )}
                    </div>
                ))}
            </main>
        </div>
    )
}
