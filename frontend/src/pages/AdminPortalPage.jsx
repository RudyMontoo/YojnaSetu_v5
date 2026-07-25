import { useState, useEffect } from 'react'
import { Mail, KeyRound, LogIn, ShieldCheck, CheckCircle2, XCircle, RefreshCw, BadgeCheck, Users, LayoutGrid, ClipboardList, Power, RotateCcw, Building2, Inbox, Trash2, PhoneCall } from 'lucide-react'
import { gateway } from '../lib/api'
import './SignInPage.css'

// Separate admin console — unlisted. Admin logs in with their (ADMIN-role) email
// OTP, then manages helper applications + existing helpers, with an overview.
export default function AdminPortalPage() {
    const [mode, setMode] = useState('loading')   // loading | login | dashboard | notadmin
    const [step, setStep] = useState('email')
    const [email, setEmail] = useState('')
    const [otp, setOtp] = useState('')
    const [tab, setTab] = useState('overview')     // overview | applications | helpers
    const [stats, setStats] = useState(null)
    const [apps, setApps] = useState([])
    const [helpers, setHelpers] = useState([])
    const [kendras, setKendras] = useState([])
    const [requests, setRequests] = useState([])
    const [issued, setIssued] = useState({})       // appId -> creds (on approve)
    const [reset, setReset] = useState({})         // helperId -> new creds (on reset-pw)
    const [expanded, setExpanded] = useState(null) // helper id whose detail is open
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(false)

    useEffect(() => { loadAll().then(ok => setMode(ok ? 'dashboard' : 'login')) }, [])

    const loadAll = async () => {
        try {
            const [s, a, h, k, r] = await Promise.all([
                gateway.adminStats(), gateway.helperApplications(), gateway.adminHelpers(),
                gateway.adminKendras(), gateway.adminAllRequests(),
            ])
            setStats(s); setApps(a.applications || []); setHelpers(h.helpers || [])
            setKendras(k.kendras || []); setRequests(r.requests || [])
            return true
        } catch (e) { if (e.status === 403) setMode('notadmin'); return false }
    }
    const deactivateKendra = async (id) => { try { await gateway.deactivateKendra(id) } finally { loadAll() } }
    const resolveReq = async (id) => { try { await gateway.resolveHelp(id) } finally { loadAll() } }
    const reopenReq = async (id) => { try { await gateway.reopenRequest(id) } finally { loadAll() } }

    const sendOtp = async (e) => { e.preventDefault(); setError(''); setBusy(true); try { await gateway.sendOtp({ email: email.trim() }); setStep('otp') } catch (err) { setError(err.message || 'Could not send OTP') } finally { setBusy(false) } }
    const verifyOtp = async (e) => { e.preventDefault(); setError(''); setBusy(true); try { await gateway.verifyOtp({ email: email.trim() }, otp.trim()); const ok = await loadAll(); setMode(ok ? 'dashboard' : 'notadmin') } catch (err) { setError(err.message || 'Incorrect OTP') } finally { setBusy(false) } }

    const approve = async (id) => { try { const r = await gateway.approveHelper(id); setIssued(s => ({ ...s, [id]: r })) } catch (e) { setError(e.message) } finally { loadAll() } }
    const rejectApp = async (id) => { try { await gateway.rejectHelper(id) } finally { loadAll() } }
    const toggleHelper = async (h) => { try { h.active ? await gateway.deactivateHelper(h.id) : await gateway.activateHelper(h.id) } finally { loadAll() } }
    const resetPw = async (h) => { try { const r = await gateway.resetHelperPassword(h.id); setReset(s => ({ ...s, [h.id]: r })) } catch (e) { setError(e.message) } finally { loadAll() } }

    // ── login / gate ──
    if (mode === 'login' || mode === 'loading') {
        return (
            <div className="signin-wrapper"><div className="signin-bg-glow" /><div className="signin-card glass-card">
                <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>Admin<span className="text-saffron"> Console</span></h1>
                <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 18 }}>Restricted — admin login required.</p>
                {error && <p className="signin-error">{error}</p>}
                {step === 'email' ? (
                    <form onSubmit={sendOtp} className="signin-form">
                        <p className="signin-label">Admin email</p>
                        <div className="signin-input-row"><span className="signin-prefix"><Mail size={15} /></span>
                            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@example.com" className="input-glass signin-input" autoFocus required /></div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || !email.trim()}>{busy ? <span className="btn-spinner" /> : 'Send OTP'}</button>
                    </form>
                ) : (
                    <form onSubmit={verifyOtp} className="signin-form">
                        <p className="signin-label">OTP sent to {email}</p>
                        <div className="signin-input-row"><span className="signin-prefix"><KeyRound size={15} /></span>
                            <input inputMode="numeric" maxLength={6} value={otp} onChange={e => setOtp(e.target.value)} placeholder="••••••" className="input-glass signin-input" style={{ letterSpacing: 8, fontWeight: 700 }} autoFocus required /></div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti" disabled={busy || otp.trim().length !== 6}>{busy ? <span className="btn-spinner" /> : <><LogIn size={16} /> Verify & Enter</>}</button>
                    </form>
                )}
            </div></div>
        )
    }
    if (mode === 'notadmin') {
        return <div className="signin-wrapper"><div className="signin-card glass-card" style={{ textAlign: 'center' }}><XCircle size={40} className="text-saffron" /><h1 className="signin-brand font-display">Not an admin account</h1><p className="signin-sub">This console is restricted to administrators.</p></div></div>
    }

    const TABS = [
        { id: 'overview', label: 'Overview', Icon: LayoutGrid },
        { id: 'applications', label: `Applications${apps.length ? ` (${apps.length})` : ''}`, Icon: ClipboardList },
        { id: 'helpers', label: `Helpers${helpers.length ? ` (${helpers.length})` : ''}`, Icon: Users },
        { id: 'kendras', label: `Kendras${kendras.length ? ` (${kendras.length})` : ''}`, Icon: Building2 },
        { id: 'requests', label: `Requests${requests.length ? ` (${requests.length})` : ''}`, Icon: Inbox },
    ]

    return (
        <div className="page-wrapper">
            <header className="glass-card" style={{ display: 'flex', alignItems: 'center', gap: 12, margin: 16, padding: '12px 16px' }}>
                <ShieldCheck size={22} className="text-saffron" />
                <div style={{ flex: 1 }}><p style={{ margin: 0, fontWeight: 700 }}>Admin Console</p><p className="text-muted" style={{ margin: 0, fontSize: 12 }}>Yojna Sarthi</p></div>
                <button className="btn btn-ghost btn-sm" onClick={loadAll}><RefreshCw size={14} /> Refresh</button>
            </header>
            <main className="page-content" style={{ paddingTop: 0 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                    {TABS.map(t => (
                        <button key={t.id} className={`btn btn-sm ${tab === t.id ? 'btn-primary btn-aarti' : 'btn-ghost'}`} onClick={() => setTab(t.id)}><t.Icon size={14} /> {t.label}</button>
                    ))}
                </div>
                {error && <p className="signin-error">{error}</p>}

                {tab === 'overview' && stats && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
                        {[
                            { label: 'On duty now', v: `${stats.helpersOnDuty ?? 0} / ${stats.helpersActive}` },
                            { label: 'Total helpers', v: stats.helpersTotal },
                            { label: 'Pending applications', v: stats.applicationsPending },
                            { label: 'Requests waiting', v: stats.requestsWaiting },
                            { label: 'Requests assigned', v: stats.requestsAssigned },
                            { label: 'Requests resolved', v: stats.requestsResolved },
                            { label: 'Registered kendras', v: stats.kendras },
                        ].map(c => (
                            <div key={c.label} className="glass-card" style={{ padding: 18, textAlign: 'center' }}>
                                <p style={{ margin: 0, fontSize: 28, fontWeight: 800 }} className="text-saffron">{c.v}</p>
                                <p className="text-muted" style={{ margin: 0, fontSize: 12 }}>{c.label}</p>
                            </div>
                        ))}
                    </div>
                )}

                {tab === 'applications' && (
                    apps.length === 0 ? <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}><p className="text-muted">No pending applications.</p></div>
                    : apps.map(a => (
                        <div key={a.id} className="glass-card" style={{ padding: 16, marginBottom: 12 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div><p style={{ margin: 0, fontWeight: 700, fontSize: 16 }}>{a.fullName}</p><a href={`tel:${a.phone}`} className="text-muted" style={{ fontSize: 13 }}>{a.phone}</a></div>
                                {a.aadhaarVerified ? <span className="badge badge-green"><BadgeCheck size={12} /> Aadhaar verified</span> : <span className="badge badge-muted">Aadhaar checksum failed</span>}
                            </div>
                            <table style={{ width: '100%', fontSize: 13, marginTop: 10 }}><tbody>
                                <tr><td className="text-muted" style={{ padding: '2px 8px 2px 0' }}>Aadhaar</td><td>{a.aadhaarMasked}</td></tr>
                                <tr><td className="text-muted" style={{ padding: '2px 8px 2px 0' }}>PAN</td><td>{a.pan}</td></tr>
                                <tr><td className="text-muted" style={{ padding: '2px 8px 2px 0' }}>Work proof</td><td>{a.workProofType}{a.workProofDetail ? ` — ${a.workProofDetail}` : ''}</td></tr>
                            </tbody></table>
                            {issued[a.id] ? (
                                <div className="glass-card glass-card-glow" style={{ padding: 12, marginTop: 12 }}>
                                    <p style={{ margin: 0, fontWeight: 600 }}><CheckCircle2 size={14} className="text-saffron" /> Helper created</p>
                                    <p style={{ margin: '6px 0', fontSize: 13 }}>ID: <b>{issued[a.id].helperId}</b> · Password: <b>{issued[a.id].tempPassword}</b></p>
                                    <p className="text-muted" style={{ fontSize: 12, margin: 0 }}>{issued[a.id].emailedTo ? `Emailed to ${issued[a.id].emailedTo}` : 'No email on file — share these with the helper.'}</p>
                                </div>
                            ) : (
                                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                                    <button className="btn btn-primary btn-aarti btn-sm" onClick={() => approve(a.id)}><CheckCircle2 size={14} /> Confirm & Issue Login</button>
                                    <button className="btn btn-ghost btn-sm" onClick={() => rejectApp(a.id)}><XCircle size={14} /> Reject</button>
                                </div>
                            )}
                        </div>
                    ))
                )}

                {tab === 'helpers' && (
                    helpers.length === 0 ? <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}><p className="text-muted">No helpers yet.</p></div>
                    : helpers.map(h => (
                        <div key={h.id} className="glass-card" style={{ padding: 14, marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div>
                                    <p style={{ margin: 0, fontWeight: 600 }}>{h.name} <span className="text-muted" style={{ fontSize: 12 }}>· {h.helperId}</span></p>
                                    <a href={`tel:${h.phone}`} className="text-muted" style={{ fontSize: 13 }}>{h.phone}</a>
                                </div>
                                <div style={{ display: 'flex', gap: 6 }}>
                                    {h.active && <span className={`badge ${h.available ? 'badge-green' : 'badge-muted'}`}>{h.available ? 'on duty' : 'away'}</span>}
                                    <span className={`badge ${h.active ? 'badge-green' : 'badge-muted'}`}>{h.active ? 'active' : 'inactive'}</span>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                                <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(expanded === h.id ? null : h.id)}>{expanded === h.id ? 'Hide' : 'View'} activity</button>
                                <button className="btn btn-ghost btn-sm" onClick={() => toggleHelper(h)}><Power size={13} /> {h.active ? 'Deactivate' : 'Activate'}</button>
                                <button className="btn btn-ghost btn-sm" onClick={() => resetPw(h)}><RotateCcw size={13} /> Reset password</button>
                            </div>
                            {expanded === h.id && (
                                <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border-glass)', fontSize: 13 }}>
                                    <p style={{ margin: '0 0 4px', fontWeight: 600 }}>Kendras ({kendras.filter(k => k.helperId === h.id && k.active).length})</p>
                                    {kendras.filter(k => k.helperId === h.id && k.active).map(k => <p key={k.id} className="text-muted" style={{ margin: 0 }}>• {k.name}</p>)}
                                    <p style={{ margin: '8px 0 4px', fontWeight: 600 }}>Handled requests ({requests.filter(r => r.assignedOperatorId === h.id).length})</p>
                                    {requests.filter(r => r.assignedOperatorId === h.id).slice(0, 5).map(r => <p key={r.id} className="text-muted" style={{ margin: 0 }}>• {r.citizenName || 'Citizen'} — {r.status}</p>)}
                                    <p className="text-muted" style={{ margin: '8px 0 0', fontSize: 12 }}>Last login: {h.lastLoginAt ? new Date(h.lastLoginAt).toLocaleString() : '—'}</p>
                                </div>
                            )}
                            {reset[h.id] && (
                                <div className="glass-card glass-card-glow" style={{ padding: 10, marginTop: 8, fontSize: 13 }}>
                                    New password: <b>{reset[h.id].tempPassword}</b> — {reset[h.id].emailedTo ? `emailed to ${reset[h.id].emailedTo}` : 'share it with the helper'}
                                </div>
                            )}
                        </div>
                    ))
                )}

                {tab === 'kendras' && (
                    kendras.length === 0 ? <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}><p className="text-muted">No registered kendras.</p></div>
                    : kendras.map(k => (
                        <div key={k.id} className="glass-card" style={{ padding: 14, marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                                <div style={{ minWidth: 0 }}>
                                    <p style={{ margin: 0, fontWeight: 600 }}>{k.name}</p>
                                    {k.address && <p className="text-muted" style={{ margin: 0, fontSize: 12 }}>{k.address}</p>}
                                    <p className="text-muted" style={{ margin: '2px 0 0', fontSize: 12 }}>by {k.helperName || k.helperId}</p>
                                </div>
                                <span className={`badge ${k.active ? 'badge-green' : 'badge-muted'}`}>{k.active ? 'active' : 'removed'}</span>
                            </div>
                            {k.active && <div style={{ marginTop: 10 }}><button className="btn btn-ghost btn-sm" onClick={() => deactivateKendra(k.id)}><Trash2 size={13} /> Deactivate</button></div>}
                        </div>
                    ))
                )}

                {tab === 'requests' && (
                    requests.length === 0 ? <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}><p className="text-muted">No help requests.</p></div>
                    : requests.map(q => (
                        <div key={q.id} className="glass-card" style={{ padding: 14, marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <div><p style={{ margin: 0, fontWeight: 600 }}>{q.citizenName || 'Citizen'}</p><a href={`tel:${q.phone}`} className="text-muted" style={{ fontSize: 13 }}>{q.phone}</a></div>
                                <span className={`badge ${q.status === 'waiting' ? 'badge-muted' : 'badge-green'}`}>{q.status}</span>
                            </div>
                            {q.message && <p style={{ fontSize: 13.5, marginTop: 8 }}>{q.message}</p>}
                            {q.status !== 'resolved' && (
                                <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                                    <a href={`tel:${q.phone}`} className="btn btn-ghost btn-sm"><PhoneCall size={13} /> Call</a>
                                    <button className="btn btn-ghost btn-sm" onClick={() => resolveReq(q.id)}><CheckCircle2 size={13} /> Force resolve</button>
                                    {q.status === 'assigned' && <button className="btn btn-ghost btn-sm" onClick={() => reopenReq(q.id)}><RotateCcw size={13} /> Reopen</button>}
                                </div>
                            )}
                        </div>
                    ))
                )}
            </main>
        </div>
    )
}
