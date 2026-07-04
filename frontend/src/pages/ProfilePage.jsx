import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    LayoutDashboard, FileText, Bookmark, Bell, Settings, LogOut,
    CheckCircle, Clock, ChevronRight, User, Globe, Smartphone, Shield,
    HeartHandshake, Upload, Loader2, IndianRupee, AlertTriangle
} from 'lucide-react'
import { getLocalUser, clearLocalUser } from '../lib/auth'
import { gateway, ai } from '../lib/api'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './ProfilePage.css'

const SIDEBAR_ITEMS = [
    { id: 'dashboard', label: 'Dashboard', Icon: LayoutDashboard },
    { id: 'applications', label: 'Applications', Icon: FileText },
    { id: 'saved', label: 'Saved Schemes', Icon: Bookmark },
    { id: 'pension', label: 'Pension Seva', Icon: HeartHandshake },
    { id: 'alerts', label: 'Alerts', Icon: Bell },
    { id: 'settings', label: 'Settings', Icon: Settings },
]

function PensionPanel() {
    const [aadhaar, setAadhaar] = useState(null)
    const [ppo, setPpo] = useState(null)
    const [busy, setBusy] = useState(false)
    const [result, setResult] = useState(null)
    const [plan, setPlan] = useState(null)
    const [planBusy, setPlanBusy] = useState(false)
    const [error, setError] = useState('')

    const check = async (e) => {
        e.preventDefault(); setBusy(true); setError(''); setResult(null)
        try { setResult(await ai.verifyPpo(aadhaar, ppo)) }
        catch (err) { setError(err.message) }
        finally { setBusy(false) }
    }
    const loadPlan = async () => {
        setPlanBusy(true); setError('')
        try { setPlan(await ai.financialPlan()) }
        catch (err) { setError(err.message) }
        finally { setPlanBusy(false) }
    }

    return (
        <div>
            <h3 className="profile-section-title">Pension Seva (Jeevan-Setu)</h3>
            {error && <p style={{ fontSize: 13, color: '#ff6b6b', marginBottom: 10 }}>{error}</p>}

            {/* PPO / Aadhaar mismatch check — #1 cause of pension DLC rejection */}
            <div className="glass-card" style={{ padding: 16, marginBottom: 16 }}>
                <p className="profile-app-name" style={{ marginBottom: 4 }}>PPO ↔ Aadhaar Match Check</p>
                <p className="text-muted" style={{ fontSize: 12.5, marginBottom: 12 }}>
                    A name or date-of-birth mismatch between your Aadhaar and PPO (Pension Payment Order)
                    is the most common reason pensions stop. Upload photos of both — we compare them.
                    Photos are never stored.
                </p>
                <form onSubmit={check} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <label className="text-muted" style={{ fontSize: 12 }}>Aadhaar card photo
                        <input className="input-glass" type="file" accept="image/*" required
                               onChange={e => setAadhaar(e.target.files[0])} style={{ width: '100%', marginTop: 4 }} />
                    </label>
                    <label className="text-muted" style={{ fontSize: 12 }}>PPO document photo
                        <input className="input-glass" type="file" accept="image/*" required
                               onChange={e => setPpo(e.target.files[0])} style={{ width: '100%', marginTop: 4 }} />
                    </label>
                    <button className="btn btn-primary btn-aarti" disabled={busy || !aadhaar || !ppo}>
                        {busy ? <><Loader2 size={15} className="spin" /> Checking (takes a minute)…</> : <><Upload size={15} /> Check Match</>}
                    </button>
                </form>
                {result && (result.checked ? (
                    <div style={{ marginTop: 14 }}>
                        <span className={`badge badge-${result.blocks_dlc_submission ? 'red' : 'green'}`}>
                            {result.blocks_dlc_submission
                                ? <><AlertTriangle size={11} /> Mismatch found — fix before DLC</>
                                : <><CheckCircle size={11} /> Records match — DLC ready</>}
                        </span>
                        <table style={{ width: '100%', fontSize: 13, marginTop: 10, borderCollapse: 'collapse' }}>
                            <tbody>
                                <tr><td className="text-subtle" style={{ padding: '3px 0' }}>Aadhaar name</td><td><b>{result.name_aadhaar}</b></td></tr>
                                <tr><td className="text-subtle" style={{ padding: '3px 0' }}>PPO name</td><td><b>{result.name_ppo}</b></td></tr>
                                <tr><td className="text-subtle" style={{ padding: '3px 0' }}>Aadhaar DOB</td><td>{result.dob_aadhaar || '—'}</td></tr>
                                <tr><td className="text-subtle" style={{ padding: '3px 0' }}>PPO DOB</td><td>{result.dob_ppo || '—'}</td></tr>
                            </tbody>
                        </table>
                        <p className="text-muted" style={{ fontSize: 12.5, marginTop: 8, whiteSpace: 'pre-wrap' }}>{result.reply}</p>
                    </div>
                ) : (
                    <p style={{ fontSize: 13, color: '#ff6b6b', marginTop: 10 }}>{result.reason}</p>
                ))}
            </div>

            {/* Annual benefit plan (Agent 7) */}
            <div className="glass-card" style={{ padding: 16 }}>
                <p className="profile-app-name" style={{ marginBottom: 4 }}>My Yearly Benefit Plan</p>
                <p className="text-muted" style={{ fontSize: 12.5, marginBottom: 12 }}>
                    Based on your profile: your total guaranteed yearly benefit across all eligible schemes,
                    and which give the most for the least paperwork.
                </p>
                <button className="btn btn-saffron-outline btn-sm" onClick={loadPlan} disabled={planBusy}>
                    {planBusy ? <><Loader2 size={14} className="spin" /> Calculating…</> : <><IndianRupee size={14} /> Show My Plan</>}
                </button>
                {plan && (
                    <div style={{ marginTop: 12 }}>
                        <p style={{ fontSize: 24, fontWeight: 800 }} className="text-saffron">
                            ₹{Number(plan.total_annual_benefit_inr).toLocaleString('en-IN')}
                            <span className="text-subtle" style={{ fontSize: 12, fontWeight: 400 }}> / year guaranteed</span>
                        </p>
                        {plan.ranked_by_benefit_effort_ratio?.slice(0, 3).map(sch => (
                            <div key={sch.schemeCode} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, borderTop: '1px solid var(--border-glass)', padding: '7px 0', fontSize: 13 }}>
                                <span>{sch.name}</span>
                                <b className="text-saffron" style={{ flexShrink: 0 }}>₹{Number(sch.annualized_inr || sch.amount_inr || 0).toLocaleString('en-IN')}</b>
                            </div>
                        ))}
                        <p className="text-muted" style={{ fontSize: 12.5, marginTop: 8, whiteSpace: 'pre-wrap' }}>{plan.reply}</p>
                    </div>
                )}
            </div>
        </div>
    )
}

function SettingsPanel({ onDeleteAccount }) {
    const [lang, setLang] = useState(() => localStorage.getItem('yojna_lang') || 'en')
    const [notif, setNotif] = useState(() => localStorage.getItem('yojna_notif') !== 'off')

    const changeLang = (v) => { setLang(v); localStorage.setItem('yojna_lang', v); window.location.reload() }
    const toggleNotif = () => { const n = !notif; setNotif(n); localStorage.setItem('yojna_notif', n ? 'on' : 'off') }

    return (
        <div>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: 'var(--text-primary)' }}>Account Settings</h3>

            {/* Language */}
            <div className="profile-setting-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%' }}>
                    <Globe size={18} className="text-saffron" />
                    <p className="profile-app-name">Preferred Language</p>
                </div>
                <select className="input-glass" value={lang} onChange={e => changeLang(e.target.value)}
                    style={{ width: '100%' }}>
                    <option value="en">English</option>
                    <option value="hi">हिन्दी</option>
                    <option value="bn">বাংলা</option>
                    <option value="ta">தமிழ்</option>
                    <option value="te">తెలుగు</option>
                    <option value="mr">मराठी</option>
                </select>
            </div>

            {/* Notifications Toggle */}
            <div className="profile-setting-row" style={{ cursor: 'pointer' }} onClick={toggleNotif}>
                <Smartphone size={18} className="text-saffron" />
                <div style={{ flex: 1 }}>
                    <p className="profile-app-name">Notifications</p>
                    <p className="text-muted" style={{ fontSize: 12 }}>{notif ? 'Enabled — you will receive alerts' : 'Disabled'}</p>
                </div>
                <div style={{ flexShrink: 0, minWidth: 40, maxWidth: 40, width: 40, height: 22, borderRadius: 11, background: notif ? 'var(--saffron)' : 'rgba(255,255,255,0.15)', position: 'relative', transition: 'background 0.2s' }}>
                    <div style={{ position: 'absolute', top: 3, left: notif ? 20 : 3, width: 16, height: 16, borderRadius: '50%', background: '#fff', transition: 'left 0.2s' }} />
                </div>
            </div>

            {/* DPDP: delete account */}
            <div className="profile-setting-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <Shield size={18} style={{ color: 'var(--red)' }} />
                    <p className="profile-app-name">Delete my account &amp; data</p>
                </div>
                <p className="text-muted" style={{ fontSize: 12, marginLeft: 28 }}>
                    Right to erasure (DPDP Act 2023): profile, applications and chat history are permanently removed.
                </p>
                <button className="btn btn-sm" style={{ marginLeft: 28, background: 'var(--red-muted)', color: 'var(--red)', border: '1px solid rgba(239,68,68,0.25)' }}
                        onClick={onDeleteAccount}>
                    Delete permanently
                </button>
            </div>

            {/* Help */}
            <div className="profile-setting-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <User size={18} className="text-saffron" />
                    <p className="profile-app-name">Help & Support</p>
                </div>
                <div style={{ marginLeft: 28 }}>
                    <p className="text-muted" style={{ fontSize: 13 }}>📞 Toll-free: <strong>1800-111-555</strong></p>
                    <p className="text-muted" style={{ fontSize: 13 }}>📧 support@yojnasetu.in</p>
                    <p className="text-muted" style={{ fontSize: 12, marginTop: 2 }}>Mon–Sat, 9am–6pm</p>
                </div>
            </div>
        </div>
    )
}

const ALERTS = [
    { text: 'PM-Kisan 16th installment released!', time: '2 hours ago', type: 'green' },
    { text: 'Your PMAY application moved to Stage 3', time: '1 day ago', type: 'saffron' },
    { text: 'New scheme for women in Maharashtra', time: '3 days ago', type: 'blue' },
    { text: 'Document expiry reminder: Income Cert.', time: '5 days ago', type: 'red' },
]

export default function ProfilePage() {
    const navigate = useNavigate()
    const [active, setActive] = useState('dashboard')
    const [profile, setProfile] = useState(null)
    const [savedSchemes, setSavedSchemes] = useState([])
    const [applications, setApplications] = useState([])
    const [loading, setLoading] = useState(true)

    const loadAll = async () => {
        setLoading(true)

        // Load local cache first for instant render
        const localUser = getLocalUser()
        if (localUser) setProfile(localUser)

        // v5.0: live profile from the Spring Boot gateway (decrypted server-side)
        try {
            const p = await gateway.getProfile()
            const profileData = {
                id: p.userId,
                phone: p.phone || localUser?.phone || '',
                name: p.name || localUser?.name || '',
                state: p.state || '',
                occupation: p.occupation || '',
                annualIncome: p.annualIncome,
                completeness: p.profileCompleteness,
            }
            setProfile(profileData)
            localStorage.setItem('yojna_user', JSON.stringify(profileData))
        } catch (e) {
            if (e.status === 401 || e.status === 403) { navigate('/signin'); return }
            // 404 = logged in, no profile document yet — that's fine
        }

        // Real applications; "saved" ones double as the saved-schemes list
        try {
            const apps = await gateway.listApplications()
            setApplications(apps)
            setSavedSchemes(apps.filter(a => a.status === 'saved')
                .map(a => ({ scheme_id: a.schemeCode, name: a.schemeName, benefit: '' })))
        } catch { setApplications([]); setSavedSchemes([]) }

        setLoading(false)
    }

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        loadAll()
    }, [])

    const handleLogout = async () => {
        try { await gateway.logout() } catch { /* cookie clear is best-effort */ }
        clearLocalUser()
        navigate('/signin')
    }

    const handleDeleteAccount = async () => {
        if (!window.confirm('This permanently deletes your profile, applications and chat history (DPDP Act right to erasure). This cannot be undone. Continue?')) return
        try {
            await gateway.deleteAccount()
            clearLocalUser()
            navigate('/signin')
        } catch (e) { alert(`Could not delete: ${e.message}`) }
    }

    const unsaveScheme = async (schemeId) => {
        const updated = savedSchemes.filter(x => x.scheme_id !== schemeId)
        setSavedSchemes(updated)
        // TODO: Call API to remove saved scheme
    }

    const [editForm, setEditForm] = useState(null)

    const initials = profile?.name
        ? profile.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
        : (getLocalUser()?.email?.[0] || '?').toUpperCase()
    const displayEmail = getLocalUser()?.phone || getLocalUser()?.email || ''

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content profile-content">

                {/* User Header */}
                <div className="glass-card profile-user-card" style={{ position: 'relative' }}>
                    <div className="sathi-tag"><Shield size={10} /> Citizen Profile</div>
                    <div className="profile-avatar">{loading ? '…' : initials}</div>
                    <div className="profile-user-info">
                        <h2 className="profile-name">{loading ? 'Loading…' : profile?.name || getLocalUser()?.name || 'Guest User'}</h2>
                        <p className="text-muted profile-meta">
                            {profile?.state && profile?.occupation
                                ? `${profile.state} • ${profile.occupation}`
                                : profile?.state || profile?.occupation || 'Complete your profile'}
                        </p>
                        <p className="text-subtle profile-phone">{displayEmail}</p>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={() => { setActive('edit'); setEditForm({ name: profile?.name || '', state: profile?.state || '', occupation: profile?.occupation || '', income: profile?.income || '', district: profile?.district || '' }) }} style={{ background: 'var(--grad-aarti)', color: '#14100a', fontWeight: 700 }}>Edit Profile</button>
                </div>

                {/* Stats Row */}
                {active === 'dashboard' && (
                    <div className="profile-stats-row">
                        {[
                            { label: 'Applied Schemes', value: applications.length, color: 'var(--saffron)' },
                            { label: 'Pending Review', value: applications.filter(a => a.status === 'pending').length, color: 'var(--gold)' },
                            { label: 'Approved', value: applications.filter(a => a.status === 'approved').length, color: 'var(--green)' },
                        ].map((stat) => (
                            <div key={stat.label} className="glass-card profile-stat-card">
                                <span className="profile-stat-val" style={{ color: stat.color }}>{stat.value}</span>
                                <span className="profile-stat-label text-muted">{stat.label}</span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Layout: sidebar + content */}
                <div className="profile-layout">
                    <aside className="profile-sidebar glass-card">
                        {SIDEBAR_ITEMS.map((item) => {
                            const BtnIcon = item.Icon
                            return (
                                <button
                                    key={item.id}
                                    className={`profile-sidebar-item ${active === item.id ? 'active' : ''}`}
                                    onClick={() => setActive(item.id)}
                                >
                                    <BtnIcon size={17} />
                                    <span>{item.label}</span>
                                </button>
                            )
                        })}
                        <div className="profile-sidebar-divider" />
                        <button className="profile-sidebar-item logout" onClick={handleLogout}>
                            <LogOut size={17} /> <span>Logout</span>
                        </button>
                    </aside>

                    <div className="profile-main-content glass-card">

                        {active === 'dashboard' && (
                            <div>
                                <h3 className="profile-section-title">Recent Applications</h3>
                                {applications.length === 0
                                    ? <p className="text-muted" style={{ fontSize: 13 }}>No applications yet. Browse schemes and apply!</p>
                                    : applications.slice(0, 3).map((app, i) => (
                                        <div key={i} className="profile-app-row" onClick={() => navigate('/status')}>
                                            <div className="profile-app-info">
                                                <p className="profile-app-name">{app.scheme_name}</p>
                                                <p className="text-muted" style={{ fontSize: 12 }}>ID: #{app.app_ref_id || app.id.slice(0, 8)}</p>
                                            </div>
                                            <span className={`badge badge-${app.status === 'approved' ? 'green' : app.status === 'pending' ? 'gold' : 'muted'}`}>
                                                {app.status}
                                            </span>
                                            <ChevronRight size={16} className="text-subtle" />
                                        </div>
                                    ))}

                                <h3 className="profile-section-title" style={{ marginTop: 24 }}>Saved for Later</h3>
                                {savedSchemes.length === 0
                                    ? <p className="text-muted" style={{ fontSize: 13 }}>No saved schemes yet. Tap 🔖 on any scheme to save!</p>
                                    : savedSchemes.slice(0, 2).map((s, i) => (
                                        <div key={i} className="profile-saved-row" onClick={() => navigate(`/schemes/${s.scheme_id}`)}>
                                            <Bookmark size={16} className="text-saffron" />
                                            <div>
                                                <p className="profile-app-name">{s.scheme_name}</p>
                                            </div>
                                        </div>
                                    ))}
                            </div>
                        )}

                        {active === 'applications' && (
                            <div>
                                <h3 className="profile-section-title">All Applications</h3>
                                {applications.length === 0
                                    ? <p className="text-muted" style={{ fontSize: 13 }}>No applications yet.</p>
                                    : applications.map((app, i) => (
                                        <div key={i} className="profile-app-row" onClick={() => navigate('/status')}>
                                            <div className="profile-app-info">
                                                <p className="profile-app-name">{app.scheme_name}</p>
                                                <p className="text-muted" style={{ fontSize: 12 }}>#{app.app_ref_id || app.id.slice(0, 8)}</p>
                                            </div>
                                            <span className={`badge badge-${app.status === 'approved' ? 'green' : 'gold'}`}>{app.status}</span>
                                            <ChevronRight size={16} className="text-subtle" />
                                        </div>
                                    ))}
                            </div>
                        )}

                        {active === 'saved' && (
                            <div>
                                <h3 className="profile-section-title">Saved Schemes</h3>
                                {savedSchemes.length === 0
                                    ? <p className="text-muted" style={{ fontSize: 13 }}>No saved schemes yet.</p>
                                    : savedSchemes.map((s, i) => (
                                        <div key={i} className="profile-saved-row">
                                            <Bookmark size={16} className="text-saffron" style={{ cursor: 'pointer' }} onClick={() => unsaveScheme(s.scheme_id)} />
                                            <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => navigate(`/schemes/${s.scheme_id}`)}>
                                                <p className="profile-app-name">{s.scheme_name}</p>
                                            </div>
                                            <ChevronRight size={16} className="text-subtle" />
                                        </div>
                                    ))}
                            </div>
                        )}

                        {active === 'alerts' && (
                            <div>
                                <h3 className="profile-section-title">Notifications</h3>
                                {ALERTS.map((a, i) => (
                                    <div key={i} className="profile-alert-row">
                                        <div className={`status-dot ${a.type === 'green' ? 'active' : a.type === 'saffron' ? 'pending' : 'failed'}`} />
                                        <div>
                                            <p className="profile-app-name">{a.text}</p>
                                            <p className="text-subtle" style={{ fontSize: 12 }}>{a.time}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {active === 'pension' && (
                            <PensionPanel />
                        )}

                        {active === 'settings' && (
                            <SettingsPanel profile={profile} />
                        )}

                        {active === 'edit' && editForm && (
                            <div>
                                <h3 className="profile-section-title">Edit Profile</h3>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                    {[['name', 'Full Name', 'text', 'Your full name'],
                                    ['state', 'State', 'text', 'Maharashtra'],
                                    ['district', 'District', 'text', 'Pune'],
                                    ['income', 'Annual Income', 'text', 'e.g. 1l-2.5l']
                                    ].map(([field, label, type, placeholder]) => (
                                        <div key={field}>
                                            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</p>
                                            <input
                                                className="input-glass"
                                                type={type}
                                                placeholder={placeholder}
                                                value={editForm[field]}
                                                onChange={e => setEditForm(f => ({ ...f, [field]: e.target.value }))}
                                                style={{ width: '100%' }}
                                            />
                                        </div>
                                    ))}
                                    <div>
                                        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Occupation</p>
                                        <select className="input-glass" value={editForm.occupation} onChange={e => setEditForm(f => ({ ...f, occupation: e.target.value }))} style={{ width: '100%' }}>
                                            <option value="farmer">Kisan (Farmer)</option>
                                            <option value="labour">Majdoor (Labour)</option>
                                            <option value="student">Student</option>
                                            <option value="business">Business</option>
                                            <option value="government">Govt Employee</option>
                                            <option value="homemaker">Homemaker</option>
                                            <option value="other">Other</option>
                                        </select>
                                    </div>
                                    <button
                                        className="btn btn-primary"
                                        style={{ marginTop: 8 }}
                                        onClick={() => {
                                            const updated = { ...profile, ...editForm }
                                            setProfile(updated)
                                            localStorage.setItem('yojna_profile', JSON.stringify(updated))
                                            // Update local user name too
                                            const lu = getLocalUser()
                                            if (lu) { lu.name = editForm.name; localStorage.setItem('yojna_user', JSON.stringify(lu)) }
                                            setActive('dashboard')
                                        }}
                                    >
                                        💾 Save Changes
                                    </button>
                                </div>
                            </div>
                        )}

                    </div>
                </div>

            </main>
            <BottomNav />
        </div>
    )
}
