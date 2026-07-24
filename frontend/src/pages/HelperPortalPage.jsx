import { useState, useEffect } from 'react'
import { KeyRound, LogIn, ShieldCheck, PhoneCall, UserCheck, CheckCircle2, RefreshCw, LogOut, Lock, MapPin, Plus, Building2 } from 'lucide-react'
import { gateway } from '../lib/api'
import './SignInPage.css'

// Separate helper portal — NOT the citizen app. Helpers log in with an
// admin-issued ID + password (no OTP, no citizen navbar), reset their password
// on first login, then handle citizen callback requests.
export default function HelperPortalPage() {
    const [mode, setMode] = useState('loading')  // loading | login | reset | dashboard
    const [helperId, setHelperId] = useState('')
    const [password, setPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [me, setMe] = useState(null)
    const [queue, setQueue] = useState([])
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)

    useEffect(() => {
        gateway.helperMe().then(h => { setMe(h); loadQueue(); setMode('dashboard') })
            .catch(() => setMode('login'))
    }, [])

    const loadQueue = async () => {
        try { const r = await gateway.helpQueue(); setQueue(r.requests || []) } catch { /* ignore */ }
    }

    const login = async (e) => {
        e.preventDefault(); setError(''); setBusy(true)
        try {
            const r = await gateway.helperLogin(helperId.trim(), password)
            setMe(r.helper)
            if (r.mustResetPassword) { setMode('reset') }
            else { await loadQueue(); setMode('dashboard') }
        } catch (err) { setError(err.message || 'Invalid helper ID or password') }
        finally { setBusy(false) }
    }

    const resetPassword = async (e) => {
        e.preventDefault(); setError(''); setBusy(true)
        try {
            await gateway.helperChangePassword(password, newPassword)  // current = the temp password used at login
            await loadQueue(); setMode('dashboard')
        } catch (err) { setError(err.message || 'Could not change password') }
        finally { setBusy(false) }
    }

    const claim = async (id) => { try { await gateway.claimHelp(id) } finally { loadQueue() } }
    const resolve = async (id) => { try { await gateway.resolveHelp(id) } finally { loadQueue() } }
    const logout = async () => { try { await gateway.helperLogout() } finally { setMe(null); setPassword(''); setMode('login') } }

    // ── Register-your-kendra state ──
    const [kName, setKName] = useState('')
    const [kAddress, setKAddress] = useState('')
    const [kPhone, setKPhone] = useState('')
    const [kServices, setKServices] = useState('')
    const [kCoords, setKCoords] = useState(null)
    const [kLocBusy, setKLocBusy] = useState(false)
    const [kBusy, setKBusy] = useState(false)
    const [kSaved, setKSaved] = useState(false)
    const [kError, setKError] = useState('')

    const useMyLocation = () => {
        if (!navigator.geolocation) { setKError('Location not available on this device.'); return }
        setKLocBusy(true); setKError('')
        navigator.geolocation.getCurrentPosition(
            (pos) => { setKCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude }); setKLocBusy(false) },
            () => { setKError('Allow location access to pin your kendra.'); setKLocBusy(false) },
            { enableHighAccuracy: true, timeout: 10000 },
        )
    }
    const registerKendra = async (e) => {
        e.preventDefault(); setKError('')
        if (!kCoords) { setKError('Tap "Use my current location" first to pin the kendra.'); return }
        setKBusy(true)
        try {
            await gateway.registerKendra({
                name: kName.trim(), address: kAddress.trim() || null, phone: kPhone.trim() || null,
                lat: kCoords.lat, lng: kCoords.lng,
                services: kServices.split(',').map(s => s.trim()).filter(Boolean),
            })
            setKSaved(true)
        } catch (err) { setKError(err.message || 'Could not register kendra') }
        finally { setKBusy(false) }
    }

    // ── login ──
    if (mode === 'login' || mode === 'loading') {
        return (
            <div className="signin-wrapper">
                <div className="signin-bg-glow" />
                <div className="signin-card glass-card">
                    <div className="signin-logo" style={{ justifyContent: 'center', marginBottom: 4 }}>
                        <div className="logo-img-circle" style={{ width: 64, height: 64 }}><img src="/logo.png" alt="" className="logo-img" /></div>
                    </div>
                    <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>Helper<span className="text-saffron"> Portal</span></h1>
                    <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 18 }}>Login with the ID & password sent to your email.</p>
                    {error && <p className="signin-error">{error}</p>}
                    <form onSubmit={login} className="signin-form">
                        <p className="signin-label">Helper ID</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><ShieldCheck size={15} /></span>
                            <input value={helperId} onChange={e => setHelperId(e.target.value)} placeholder="HLP-XXXXX" className="input-glass signin-input" autoFocus required />
                        </div>
                        <p className="signin-label">Password</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><KeyRound size={15} /></span>
                            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" className="input-glass signin-input" required />
                        </div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || !helperId.trim() || !password}>
                            {busy ? <span className="btn-spinner" /> : <><LogIn size={16} /> Login</>}
                        </button>
                    </form>
                </div>
            </div>
        )
    }

    // ── forced password reset ──
    if (mode === 'reset') {
        return (
            <div className="signin-wrapper">
                <div className="signin-bg-glow" />
                <div className="signin-card glass-card">
                    <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>Set a new password</h1>
                    <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 18 }}>Please replace the temporary password before you continue.</p>
                    {error && <p className="signin-error">{error}</p>}
                    <form onSubmit={resetPassword} className="signin-form">
                        <p className="signin-label">New password (min 6 chars)</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><Lock size={15} /></span>
                            <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="••••••••" className="input-glass signin-input" autoFocus required />
                        </div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || newPassword.length < 6}>
                            {busy ? <span className="btn-spinner" /> : <>Save & Continue</>}
                        </button>
                    </form>
                </div>
            </div>
        )
    }

    // ── dashboard ──
    return (
        <div className="page-wrapper">
            <header className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: 12, margin: 16, padding: '12px 16px' }}>
                <div className="logo-img-circle" style={{ width: 40, height: 40 }}><img src="/logo.png" alt="" className="logo-img" /></div>
                <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontWeight: 700 }}>Helper Portal</p>
                    <p className="text-muted" style={{ margin: 0, fontSize: 12 }}>{me?.name} · {me?.helperId}</p>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={logout}><LogOut size={14} /> Logout</button>
            </header>
            <main className="page-content" style={{ paddingTop: 0 }}>
                {/* Register your Kendra — makes it appear "Connected with us" for nearby citizens */}
                <div className="glass-card" style={{ padding: 18, marginBottom: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <Building2 size={18} className="text-saffron" />
                        <h2 style={{ margin: 0, fontSize: 16 }}>Register your Kendra</h2>
                    </div>
                    <p className="text-muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 12 }}>
                        Pin your Jan Seva Kendra so nearby citizens see it marked "Connected with us".
                    </p>
                    {kSaved ? (
                        <div style={{ textAlign: 'center', padding: '6px 0' }}>
                            <CheckCircle2 size={30} className="text-saffron" />
                            <p style={{ fontWeight: 600, marginTop: 6 }}>Kendra registered! It now shows for citizens near you.</p>
                        </div>
                    ) : (
                        <form onSubmit={registerKendra}>
                            {kError && <p className="signin-error" style={{ marginBottom: 8 }}>{kError}</p>}
                            <input className="input-glass" placeholder="Kendra name" value={kName} onChange={e => setKName(e.target.value)} style={{ width: '100%', marginBottom: 8 }} required />
                            <input className="input-glass" placeholder="Address (optional)" value={kAddress} onChange={e => setKAddress(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
                            <input className="input-glass" inputMode="tel" placeholder="Phone (optional)" value={kPhone} onChange={e => setKPhone(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
                            <input className="input-glass" placeholder="Services, comma separated (e.g. PM-Kisan, Aadhaar)" value={kServices} onChange={e => setKServices(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
                            <button type="button" className="btn btn-ghost btn-sm" onClick={useMyLocation} disabled={kLocBusy} style={{ width: '100%', marginBottom: 10 }}>
                                {kLocBusy ? <span className="btn-spinner" /> : <><MapPin size={14} /> {kCoords ? 'Location pinned ✓' : 'Use my current location'}</>}
                            </button>
                            <button type="submit" className="btn btn-primary btn-aarti" style={{ width: '100%' }} disabled={kBusy || !kName.trim() || !kCoords}>
                                {kBusy ? <span className="btn-spinner" /> : <><Plus size={15} /> Register Kendra</>}
                            </button>
                        </form>
                    )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                    <PhoneCall size={18} className="text-saffron" />
                    <h1 style={{ margin: 0, fontSize: 20 }}>Citizen Help Requests{queue.length > 0 ? ` (${queue.length})` : ''}</h1>
                    <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }} onClick={loadQueue}><RefreshCw size={13} /> Refresh</button>
                </div>
                {queue.length === 0 ? (
                    <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}>
                        <p className="text-muted">No pending callback requests right now. 🎉</p>
                    </div>
                ) : queue.map(q => (
                    <div key={q.id} className="glass-card" style={{ padding: 14, marginBottom: 10 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                            <div>
                                <p style={{ margin: 0, fontWeight: 600 }}>{q.citizenName || 'Citizen'}</p>
                                <a href={`tel:${q.phone}`} className="text-muted" style={{ fontSize: 13 }}>{q.phone}</a>
                            </div>
                            <span className={`badge ${q.status === 'assigned' ? 'badge-green' : 'badge-muted'}`}>{q.status}</span>
                        </div>
                        {q.message && <p style={{ fontSize: 14, marginTop: 8 }}>{q.message}</p>}
                        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                            <a href={`tel:${q.phone}`} className="btn btn-primary btn-sm"><PhoneCall size={13} /> Call</a>
                            {q.status === 'waiting' && <button className="btn btn-ghost btn-sm" onClick={() => claim(q.id)}><UserCheck size={13} /> Claim</button>}
                            <button className="btn btn-ghost btn-sm" onClick={() => resolve(q.id)}><CheckCircle2 size={13} /> Resolve</button>
                        </div>
                    </div>
                ))}
            </main>
        </div>
    )
}
