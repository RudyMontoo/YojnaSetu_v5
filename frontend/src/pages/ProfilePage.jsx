import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    LayoutDashboard, FileText, Bookmark, Bell, Settings, LogOut,
    CheckCircle, Clock, ChevronRight, User, Globe, Smartphone, Shield
} from 'lucide-react'
import { getLocalUser, clearLocalUser } from '../lib/auth'
import { supabase } from '../lib/supabase'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './ProfilePage.css'

const SIDEBAR_ITEMS = [
    { id: 'dashboard', label: 'Dashboard', Icon: LayoutDashboard },
    { id: 'applications', label: 'Applications', Icon: FileText },
    { id: 'saved', label: 'Saved Schemes', Icon: Bookmark },
    { id: 'alerts', label: 'Alerts', Icon: Bell },
    { id: 'settings', label: 'Settings', Icon: Settings },
]

function SettingsPanel() {
    const [lang, setLang] = useState(() => localStorage.getItem('yojna_lang') || 'hi-en')
    const [notif, setNotif] = useState(() => localStorage.getItem('yojna_notif') !== 'off')
    const [showPwd, setShowPwd] = useState(false)
    const [oldPwd, setOldPwd] = useState('')
    const [newPwd, setNewPwd] = useState('')
    const [pwdMsg, setPwdMsg] = useState('')

    const changeLang = (v) => { setLang(v); localStorage.setItem('yojna_lang', v) }
    const toggleNotif = () => { const n = !notif; setNotif(n); localStorage.setItem('yojna_notif', n ? 'on' : 'off') }
    const changePwd = async () => {
        if (newPwd.length < 6) { setPwdMsg('❌ New password must be 6+ characters'); return }
        try {
            const { error } = await supabase.auth.updateUser({ password: newPwd })
            if (error) throw error
            setPwdMsg('✅ Password updated!')
            setOldPwd(''); setNewPwd('')
        } catch (err) {
            setPwdMsg(`❌ ${err.message}`)
        }
    }

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
                    <option value="hi-en">Hindi + English (Hinglish)</option>
                    <option value="hi">Hindi only</option>
                    <option value="en">English only</option>
                    <option value="mr">Marathi</option>
                    <option value="ta">Tamil</option>
                    <option value="te">Telugu</option>
                    <option value="bn">Bengali</option>
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

            {/* Change Password */}
            <div className="profile-setting-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', cursor: 'pointer' }} onClick={() => setShowPwd(s => !s)}>
                    <Shield size={18} className="text-saffron" />
                    <div style={{ flex: 1 }}><p className="profile-app-name">Change Password</p></div>
                    <ChevronRight size={16} className="text-subtle" style={{ transform: showPwd ? 'rotate(90deg)' : 'none', transition: '0.2s' }} />
                </div>
                {showPwd && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%', marginLeft: 28 }}>
                        <input className="input-glass" type="password" placeholder="Current password" value={oldPwd} onChange={e => setOldPwd(e.target.value)} style={{ width: '100%' }} />
                        <input className="input-glass" type="password" placeholder="New password (min 6 chars)" value={newPwd} onChange={e => setNewPwd(e.target.value)} style={{ width: '100%' }} />
                        <button className="btn btn-saffron-outline btn-sm" onClick={changePwd}>Update Password</button>
                        {pwdMsg && <p style={{ fontSize: 13, color: pwdMsg.startsWith('✅') ? 'var(--green, #4caf50)' : '#ff6b6b' }}>{pwdMsg}</p>}
                    </div>
                )}
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

        // Get live session from Supabase
        try {
            const { data: { session } } = await supabase.auth.getSession()
            if (session?.user) {
                const u = session.user
                const meta = u.user_metadata || {}
                const profileData = {
                    id: u.id,
                    email: u.email,
                    name: meta.name || meta.full_name || localUser?.name || '',
                    state: meta.state || localUser?.state || '',
                    language: meta.language || localUser?.language || 'hi-IN',
                    age: meta.age || localUser?.age || '',
                }
                setProfile(profileData)
                localStorage.setItem('yojna_user', JSON.stringify(profileData))
            }
        } catch (e) {
            console.error('Failed to load Supabase session', e)
        }

        // Load saved schemes from localStorage
        try {
            const localSaved = JSON.parse(localStorage.getItem('yojna_saved') || '[]')
            setSavedSchemes(localSaved)
        } catch { setSavedSchemes([]) }

        setApplications([])
        setLoading(false)
    }

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        loadAll()
    }, [])

    const handleLogout = async () => {
        await supabase.auth.signOut()
        clearLocalUser()
        navigate('/signin')
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
    const displayEmail = getLocalUser()?.email || ''

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content profile-content">

                {/* User Header */}
                <div className="glass-card profile-user-card">
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
                    <button className="btn btn-ghost btn-sm" onClick={() => { setActive('edit'); setEditForm({ name: profile?.name || '', state: profile?.state || '', occupation: profile?.occupation || '', income: profile?.income || '', district: profile?.district || '' }) }}>Edit Profile</button>
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
