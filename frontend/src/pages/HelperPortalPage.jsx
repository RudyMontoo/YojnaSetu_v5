import { useState, useEffect } from 'react'
import {
    KeyRound, LogIn, ShieldCheck, PhoneCall, UserCheck, CheckCircle2, RefreshCw, LogOut, Lock,
    MapPin, Plus, Building2, Trash2, Search, XCircle, Sparkles, History, Inbox, FileText,
} from 'lucide-react'
import { gateway, ai } from '../lib/api'
import './SignInPage.css'

const DOC_TYPES = [
    { value: 'aadhaar', label: 'Aadhaar Card' }, { value: 'pan', label: 'PAN Card' },
    { value: 'voter_id', label: 'Voter ID' }, { value: 'ration_card', label: 'Ration Card' },
    { value: 'income_cert', label: 'Income Certificate' }, { value: 'caste_cert', label: 'Caste Certificate' },
    { value: 'disability_cert', label: 'Disability Certificate' }, { value: 'land_record', label: 'Land Record' },
    { value: 'bank_passbook', label: 'Bank Passbook' },
]

// Separate helper portal (unlisted). Admin-issued ID+password login (ROLE_HELPER,
// no OTP) -> forced first-login reset -> a workspace: callback queue, kendra
// registry, CSC doc-alternatives tool, and account.
export default function HelperPortalPage() {
    const [mode, setMode] = useState('loading')   // loading | login | reset | dashboard
    const [helperId, setHelperId] = useState('')
    const [password, setPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [me, setMe] = useState(null)
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)
    const [tab, setTab] = useState('requests')    // requests | kendras | doc | account

    const [queue, setQueue] = useState([])
    const [myKendras, setMyKendras] = useState([])
    const [handled, setHandled] = useState([])

    useEffect(() => {
        gateway.helperMe().then(h => { setMe(h); loadAll(); setMode('dashboard') }).catch(() => setMode('login'))
    }, [])

    const loadAll = async () => {
        try { const q = await gateway.helpQueue(); setQueue(q.requests || []) } catch { /* */ }
        try { const k = await gateway.myKendras(); setMyKendras(k.kendras || []) } catch { /* */ }
        try { const h = await gateway.myHandled(); setHandled(h.requests || []) } catch { /* */ }
    }

    const login = async (e) => {
        e.preventDefault(); setError(''); setBusy(true)
        try {
            const r = await gateway.helperLogin(helperId.trim(), password)
            setMe(r.helper)
            if (r.mustResetPassword) setMode('reset'); else { await loadAll(); setMode('dashboard') }
        } catch (err) { setError(err.message || 'Invalid helper ID or password') } finally { setBusy(false) }
    }
    const resetPassword = async (e) => {
        e.preventDefault(); setError(''); setBusy(true)
        try { await gateway.helperChangePassword(password, newPassword); await loadAll(); setMode('dashboard') }
        catch (err) { setError(err.message || 'Could not change password') } finally { setBusy(false) }
    }
    const claim = async (id) => { try { await gateway.claimHelp(id) } finally { loadAll() } }
    const resolve = async (id) => { try { await gateway.resolveHelp(id) } finally { loadAll() } }
    const logout = async () => { try { await gateway.helperLogout() } finally { setMe(null); setPassword(''); setMode('login') } }

    // ── register-your-kendra ──
    const [kName, setKName] = useState(''); const [kAddress, setKAddress] = useState(''); const [kPhone, setKPhone] = useState('')
    const [kServices, setKServices] = useState(''); const [kCoords, setKCoords] = useState(null)
    const [kLocBusy, setKLocBusy] = useState(false); const [kBusy, setKBusy] = useState(false); const [kError, setKError] = useState('')
    const useMyLocation = () => {
        if (!navigator.geolocation) { setKError('Location not available.'); return }
        setKLocBusy(true); setKError('')
        navigator.geolocation.getCurrentPosition(
            p => { setKCoords({ lat: p.coords.latitude, lng: p.coords.longitude }); setKLocBusy(false) },
            () => { setKError('Allow location to pin your kendra.'); setKLocBusy(false) }, { enableHighAccuracy: true, timeout: 10000 })
    }
    const registerKendra = async (e) => {
        e.preventDefault(); setKError('')
        if (!kCoords) { setKError('Tap "Use my current location" first.'); return }
        setKBusy(true)
        try {
            await gateway.registerKendra({ name: kName.trim(), address: kAddress.trim() || null, phone: kPhone.trim() || null, lat: kCoords.lat, lng: kCoords.lng, services: kServices.split(',').map(s => s.trim()).filter(Boolean) })
            setKName(''); setKAddress(''); setKPhone(''); setKServices(''); setKCoords(null); loadAll()
        } catch (err) { setKError(err.message || 'Could not register kendra') } finally { setKBusy(false) }
    }
    const removeKendra = async (id) => { try { await gateway.deactivateKendra(id) } finally { loadAll() } }

    // ── doc helper (CSC alternatives) ──
    const [schemeCode, setSchemeCode] = useState(''); const [docType, setDocType] = useState(DOC_TYPES[0].value)
    const [docResult, setDocResult] = useState(null); const [docBusy, setDocBusy] = useState(false); const [docError, setDocError] = useState('')
    const findAlternatives = async (e) => {
        e.preventDefault(); if (!schemeCode.trim()) return
        setDocBusy(true); setDocError(''); setDocResult(null)
        try { setDocResult(await ai.cscAlternatives(schemeCode.trim(), docType)) }
        catch (err) { setDocError(err.status === 404 ? `No scheme found for "${schemeCode.trim()}"` : (err.message || 'Could not reach the service')) }
        finally { setDocBusy(false) }
    }

    // ── account: change password ──
    const [curPw, setCurPw] = useState(''); const [nextPw, setNextPw] = useState(''); const [pwMsg, setPwMsg] = useState(''); const [pwBusy, setPwBusy] = useState(false)
    const changePw = async (e) => {
        e.preventDefault(); setPwMsg(''); setPwBusy(true)
        try { await gateway.helperChangePassword(curPw, nextPw); setPwMsg('✓ Password updated'); setCurPw(''); setNextPw('') }
        catch (err) { setPwMsg(err.message || 'Could not change password') } finally { setPwBusy(false) }
    }

    // ── login / reset screens ──
    if (mode === 'login' || mode === 'loading') {
        return (
            <div className="signin-wrapper"><div className="signin-bg-glow" /><div className="signin-card glass-card">
                <div className="signin-logo" style={{ justifyContent: 'center', marginBottom: 4 }}><div className="logo-img-circle" style={{ width: 64, height: 64 }}><img src="/logo.png" alt="" className="logo-img" /></div></div>
                <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>Helper<span className="text-saffron"> Portal</span></h1>
                <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 18 }}>Login with the ID & password sent to your email.</p>
                {error && <p className="signin-error">{error}</p>}
                <form onSubmit={login} className="signin-form">
                    <p className="signin-label">Helper ID</p>
                    <div className="signin-input-row"><span className="signin-prefix"><ShieldCheck size={15} /></span><input value={helperId} onChange={e => setHelperId(e.target.value)} placeholder="HLP-XXXXX" className="input-glass signin-input" autoFocus required /></div>
                    <p className="signin-label">Password</p>
                    <div className="signin-input-row"><span className="signin-prefix"><KeyRound size={15} /></span><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" className="input-glass signin-input" required /></div>
                    <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || !helperId.trim() || !password}>{busy ? <span className="btn-spinner" /> : <><LogIn size={16} /> Login</>}</button>
                </form>
            </div></div>
        )
    }
    if (mode === 'reset') {
        return (
            <div className="signin-wrapper"><div className="signin-bg-glow" /><div className="signin-card glass-card">
                <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>Set a new password</h1>
                <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 18 }}>Replace the temporary password to continue.</p>
                {error && <p className="signin-error">{error}</p>}
                <form onSubmit={resetPassword} className="signin-form">
                    <p className="signin-label">New password (min 6 chars)</p>
                    <div className="signin-input-row"><span className="signin-prefix"><Lock size={15} /></span><input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="••••••••" className="input-glass signin-input" autoFocus required /></div>
                    <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || newPassword.length < 6}>{busy ? <span className="btn-spinner" /> : 'Save & Continue'}</button>
                </form>
            </div></div>
        )
    }

    const TABS = [
        { id: 'requests', label: `Requests${queue.length ? ` (${queue.length})` : ''}`, Icon: Inbox },
        { id: 'kendras', label: 'My Kendras', Icon: Building2 },
        { id: 'doc', label: 'Doc Helper', Icon: FileText },
        { id: 'account', label: 'Account', Icon: History },
    ]

    return (
        <div className="page-wrapper">
            <header className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: 12, margin: 16, padding: '12px 16px' }}>
                <div className="logo-img-circle" style={{ width: 40, height: 40 }}><img src="/logo.png" alt="" className="logo-img" /></div>
                <div style={{ flex: 1 }}><p style={{ margin: 0, fontWeight: 700 }}>Helper Portal</p><p className="text-muted" style={{ margin: 0, fontSize: 12 }}>{me?.name} · {me?.helperId}</p></div>
                <button className="btn btn-ghost btn-sm" onClick={loadAll}><RefreshCw size={14} /></button>
                <button className="btn btn-ghost btn-sm" onClick={logout}><LogOut size={14} /> Logout</button>
            </header>
            <main className="page-content" style={{ paddingTop: 0 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                    {TABS.map(t => <button key={t.id} className={`btn btn-sm ${tab === t.id ? 'btn-primary btn-aarti' : 'btn-ghost'}`} onClick={() => setTab(t.id)}><t.Icon size={14} /> {t.label}</button>)}
                </div>

                {/* ── Requests queue ── */}
                {tab === 'requests' && (queue.length === 0
                    ? <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}><p className="text-muted">No pending callback requests. 🎉</p></div>
                    : queue.map(q => (
                        <div key={q.id} className="glass-card" style={{ padding: 14, marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div><p style={{ margin: 0, fontWeight: 600 }}>{q.citizenName || 'Citizen'}</p><a href={`tel:${q.phone}`} className="text-muted" style={{ fontSize: 13 }}>{q.phone}</a></div>
                                <span className={`badge ${q.status === 'assigned' ? 'badge-green' : 'badge-muted'}`}>{q.status}</span>
                            </div>
                            {q.message && <p style={{ fontSize: 14, marginTop: 8 }}>{q.message}</p>}
                            <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                                <a href={`tel:${q.phone}`} className="btn btn-primary btn-sm"><PhoneCall size={13} /> Call</a>
                                {q.status === 'waiting' && <button className="btn btn-ghost btn-sm" onClick={() => claim(q.id)}><UserCheck size={13} /> Claim</button>}
                                <button className="btn btn-ghost btn-sm" onClick={() => resolve(q.id)}><CheckCircle2 size={13} /> Resolve</button>
                            </div>
                        </div>
                    )))}

                {/* ── My Kendras (register + list) ── */}
                {tab === 'kendras' && <>
                    <div className="glass-card" style={{ padding: 18, marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}><Building2 size={18} className="text-saffron" /><h2 style={{ margin: 0, fontSize: 16 }}>Register a Kendra</h2></div>
                        <p className="text-muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 12 }}>Pin your Jan Seva Kendra so nearby citizens see it "Connected with us".</p>
                        <form onSubmit={registerKendra}>
                            {kError && <p className="signin-error" style={{ marginBottom: 8 }}>{kError}</p>}
                            <input className="input-glass" placeholder="Kendra name" value={kName} onChange={e => setKName(e.target.value)} style={{ width: '100%', marginBottom: 8 }} required />
                            <input className="input-glass" placeholder="Address (optional)" value={kAddress} onChange={e => setKAddress(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
                            <input className="input-glass" inputMode="tel" placeholder="Phone (optional)" value={kPhone} onChange={e => setKPhone(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
                            <input className="input-glass" placeholder="Services, comma separated" value={kServices} onChange={e => setKServices(e.target.value)} style={{ width: '100%', marginBottom: 8 }} />
                            <button type="button" className="btn btn-ghost btn-sm" onClick={useMyLocation} disabled={kLocBusy} style={{ width: '100%', marginBottom: 10 }}>{kLocBusy ? <span className="btn-spinner" /> : <><MapPin size={14} /> {kCoords ? 'Location pinned ✓' : 'Use my current location'}</>}</button>
                            <button type="submit" className="btn btn-primary btn-aarti" style={{ width: '100%' }} disabled={kBusy || !kName.trim() || !kCoords}>{kBusy ? <span className="btn-spinner" /> : <><Plus size={15} /> Register Kendra</>}</button>
                        </form>
                    </div>
                    <h3 style={{ fontSize: 15, marginBottom: 8 }}>My Kendras ({myKendras.length})</h3>
                    {myKendras.length === 0 ? <p className="text-muted" style={{ fontSize: 13 }}>None yet.</p>
                        : myKendras.map(k => (
                            <div key={k.id} className="glass-card" style={{ padding: 12, marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                                <div style={{ minWidth: 0 }}><p style={{ margin: 0, fontWeight: 600 }}>{k.name}</p>{k.address && <p className="text-muted" style={{ margin: 0, fontSize: 12 }}>{k.address}</p>}</div>
                                <button className="btn btn-ghost btn-sm" style={{ flexShrink: 0 }} onClick={() => removeKendra(k.id)}><Trash2 size={13} /> Remove</button>
                            </div>
                        ))}
                </>}

                {/* ── Doc Helper (Agent 9) ── */}
                {tab === 'doc' && <>
                    <div className="glass-card" style={{ padding: 18, marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}><FileText size={18} className="text-saffron" /><h2 style={{ margin: 0, fontSize: 16 }}>Missing Document Helper</h2></div>
                        <p className="text-muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 12 }}>Citizen missing a document? Find a real, accepted alternative before turning them away.</p>
                        <form onSubmit={findAlternatives}>
                            {docError && <p className="signin-error" style={{ marginBottom: 8 }}>{docError}</p>}
                            <input className="input-glass" placeholder="Scheme code (e.g. central-agriculture-pm-kisan-samman-nidhi)" value={schemeCode} onChange={e => setSchemeCode(e.target.value)} style={{ width: '100%', marginBottom: 8 }} required />
                            <select className="input-glass" value={docType} onChange={e => setDocType(e.target.value)} style={{ width: '100%', marginBottom: 10 }}>{DOC_TYPES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}</select>
                            <button type="submit" className="btn btn-primary btn-aarti" style={{ width: '100%' }} disabled={docBusy || !schemeCode.trim()}>{docBusy ? <span className="btn-spinner" /> : <><Search size={15} /> Find Alternatives</>}</button>
                        </form>
                    </div>
                    {docResult && (
                        <div className="glass-card glass-card-glow" style={{ padding: 16 }}>
                            <h3 style={{ marginTop: 0 }}>{docResult.scheme_name}</h3>
                            {docResult.mandatory_no_substitute ? <p style={{ color: 'var(--red)' }}><XCircle size={15} /> Mandatory — no substitute accepted</p>
                                : docResult.has_alternatives ? <p className="text-saffron"><CheckCircle2 size={15} /> Alternatives available</p>
                                : <p style={{ color: 'var(--red)' }}><XCircle size={15} /> No realistic alternative found</p>}
                            {docResult.alternatives?.map((alt, i) => (
                                <div key={i} style={{ marginTop: 8 }}><p style={{ margin: 0, fontWeight: 600 }}><Sparkles size={12} className="text-saffron" /> {alt.document}</p><p className="text-muted" style={{ margin: 0, fontSize: 13 }}>{alt.how_to_get}</p></div>
                            ))}
                            {docResult.operator_advice && <p style={{ fontSize: 13.5, marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border-glass)' }}>{docResult.operator_advice}</p>}
                        </div>
                    )}
                </>}

                {/* ── Account (handled history + change password) ── */}
                {tab === 'account' && <>
                    <div className="glass-card" style={{ padding: 18, marginBottom: 16 }}>
                        <h2 style={{ margin: '0 0 12px', fontSize: 16 }}>Change password</h2>
                        <form onSubmit={changePw}>
                            {pwMsg && <p className={pwMsg.startsWith('✓') ? 'text-saffron' : 'signin-error'} style={{ marginBottom: 8 }}>{pwMsg}</p>}
                            <input className="input-glass" type="password" placeholder="Current password" value={curPw} onChange={e => setCurPw(e.target.value)} style={{ width: '100%', marginBottom: 8 }} required />
                            <input className="input-glass" type="password" placeholder="New password (min 6)" value={nextPw} onChange={e => setNextPw(e.target.value)} style={{ width: '100%', marginBottom: 10 }} required />
                            <button type="submit" className="btn btn-primary btn-aarti" style={{ width: '100%' }} disabled={pwBusy || nextPw.length < 6}>{pwBusy ? <span className="btn-spinner" /> : 'Update password'}</button>
                        </form>
                    </div>
                    <h3 style={{ fontSize: 15, marginBottom: 8 }}>My handled requests ({handled.length})</h3>
                    {handled.length === 0 ? <p className="text-muted" style={{ fontSize: 13 }}>None yet.</p>
                        : handled.map(q => (
                            <div key={q.id} className="glass-card" style={{ padding: 12, marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div><p style={{ margin: 0, fontWeight: 600 }}>{q.citizenName || 'Citizen'}</p><span className="text-muted" style={{ fontSize: 12 }}>{q.phone}</span></div>
                                <span className={`badge ${q.status === 'resolved' ? 'badge-green' : 'badge-muted'}`}>{q.status}</span>
                            </div>
                        ))}
                </>}
            </main>
        </div>
    )
}
