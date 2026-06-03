import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Users, CheckCircle, XCircle, Clock, Star,
    Phone, MapPin, Languages, LogOut, RefreshCw,
    ChevronDown, ChevronUp, Shield, Briefcase
} from 'lucide-react'
import './HelperDashboardPage.css'

const STATUS_CONFIG = {
    pending:  { label: 'Pending',  color: '#f59e0b', icon: Clock       },
    accepted: { label: 'Accepted', color: '#4ade80', icon: CheckCircle },
    declined: { label: 'Declined', color: '#f87171', icon: XCircle     },
}

function StatCard({ icon: Icon, label, value, accent }) {
    return (
        <div className="hd-stat-card glass-card" style={{ '--accent': accent }}>
            <div className="hd-stat-icon"><Icon size={20} /></div>
            <div>
                <div className="hd-stat-value">{value}</div>
                <div className="hd-stat-label">{label}</div>
            </div>
        </div>
    )
}

function AppointmentCard({ appt }) {
    const [expanded, setExpanded] = useState(false)
    const cfg = STATUS_CONFIG[appt.status] || STATUS_CONFIG.pending
    const Icon = cfg.icon

    return (
        <div className={`hd-appt-card glass-card status-${appt.status}`}>
            <div className="hd-appt-header" onClick={() => setExpanded(e => !e)}>
                <div className="hd-appt-left">
                    <div className="hd-appt-status-icon" style={{ color: cfg.color }}>
                        <Icon size={18} />
                    </div>
                    <div>
                        <p className="hd-appt-name">{appt.citizen_name}</p>
                        <p className="hd-appt-scheme text-muted">{appt.scheme_name}</p>
                    </div>
                </div>
                <div className="hd-appt-right">
                    <span className="hd-appt-badge" style={{ background: `${cfg.color}22`, color: cfg.color, border: `1px solid ${cfg.color}44` }}>
                        {cfg.label}
                    </span>
                    {expanded ? <ChevronUp size={16} className="text-muted" /> : <ChevronDown size={16} className="text-muted" />}
                </div>
            </div>

            {expanded && (
                <div className="hd-appt-details">
                    <div className="hd-appt-detail-row">
                        <Phone size={13} className="text-muted" />
                        <a href={`tel:${appt.citizen_phone}`} className="text-saffron hd-phone-link">
                            {appt.citizen_phone}
                        </a>
                    </div>
                    {appt.message && (
                        <div className="hd-appt-detail-row">
                            <span className="text-muted" style={{ fontSize: 13 }}>💬 {appt.message}</span>
                        </div>
                    )}
                    <div className="hd-appt-detail-row">
                        <Clock size={13} className="text-muted" />
                        <span className="text-subtle" style={{ fontSize: 12 }}>
                            {new Date(appt.created_at).toLocaleString('en-IN')}
                        </span>
                    </div>
                    {appt.status === 'accepted' && (
                        <a href={`tel:${appt.citizen_phone}`} className="btn btn-primary btn-sm hd-call-btn">
                            <Phone size={13} /> Call Now
                        </a>
                    )}
                </div>
            )}
        </div>
    )
}

export default function HelperDashboardPage() {
    const navigate = useNavigate()
    const [helper, setHelper]         = useState(null)
    const [appts, setAppts]           = useState([])
    const [stats, setStats]           = useState({})
    const [loading, setLoading]       = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [filter, setFilter]         = useState('all')

    const loadDashboard = async (h) => {
        try {
            const res  = await fetch(`/sahayak/helper/dashboard/${h.id}`)
            const data = await res.json()
            if (res.ok) {
                setAppts(data.appointments || [])
                setStats(data.stats || {})
            }
        } catch {}
    }

    useEffect(() => {
        const stored = localStorage.getItem('yojna_helper')
        if (!stored) { navigate('/helper-login'); return }
        const h = JSON.parse(stored)
        setHelper(h)
        loadDashboard(h).finally(() => setLoading(false))
    }, [navigate])

    const refresh = async () => {
        if (!helper) return
        setRefreshing(true)
        await loadDashboard(helper)
        setRefreshing(false)
    }

    const logout = () => {
        localStorage.removeItem('yojna_helper')
        navigate('/helper-login')
    }

    const filtered = filter === 'all' ? appts : appts.filter(a => a.status === filter)

    if (loading) {
        return (
            <div className="hd-loading">
                <div className="hd-loading-spinner" />
                <p className="text-muted">Loading your dashboard...</p>
            </div>
        )
    }

    return (
        <div className="hd-wrapper">
            {/* ── Sidebar (desktop) / Top bar (mobile) ── */}
            <aside className="hd-sidebar glass-card">
                <div className="hd-sidebar-brand">
                    <Shield size={22} className="text-saffron" />
                    <span>Jan Sahayak</span>
                </div>

                <div className="hd-profile-card">
                    <div className="hd-avatar">
                        {helper?.name?.charAt(0).toUpperCase()}
                    </div>
                    <div className="hd-profile-info">
                        <p className="hd-profile-name">{helper?.name}</p>
                        <p className="hd-profile-code text-subtle">{helper?.helper_code}</p>
                    </div>
                </div>

                <div className="hd-sidebar-stats">
                    <div className="hd-mini-stat">
                        <span className="text-muted" style={{ fontSize: 12 }}>Rating</span>
                        <span className="hd-mini-val">
                            <Star size={12} fill="#F59E0B" stroke="#F59E0B" /> {helper?.rating}
                        </span>
                    </div>
                    <div className="hd-mini-stat">
                        <span className="text-muted" style={{ fontSize: 12 }}>Total Helped</span>
                        <span className="hd-mini-val">{helper?.total_helped}</span>
                    </div>
                </div>

                <div className="hd-sidebar-meta">
                    <div className="hd-meta-row"><MapPin size={13} /> {helper?.district}, {helper?.state}</div>
                    <div className="hd-meta-row"><Languages size={13} /> {helper?.languages?.join(', ')}</div>
                    <div className="hd-meta-row"><Briefcase size={13} /> {helper?.services?.length} services</div>
                </div>

                <button className="btn btn-ghost hd-logout-btn" onClick={logout}>
                    <LogOut size={15} /> Sign Out
                </button>
            </aside>

            {/* ── Main content ── */}
            <main className="hd-main">
                {/* Mobile header */}
                <div className="hd-mobile-header">
                    <div className="hd-sidebar-brand">
                        <Shield size={18} className="text-saffron" />
                        <span>Jan Sahayak</span>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={logout}>
                        <LogOut size={14} />
                    </button>
                </div>

                {/* Greeting */}
                <div className="hd-greeting">
                    <div>
                        <h1 className="hd-greeting-title">
                            Namaste, <span className="text-saffron">{helper?.name?.split(' ')[0]}</span> 🙏
                        </h1>
                        <p className="text-muted hd-greeting-sub">
                            Here are your appointment requests.
                        </p>
                    </div>
                    <button className="btn btn-ghost btn-sm hd-refresh-btn" onClick={refresh} disabled={refreshing}>
                        <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
                        {refreshing ? 'Refreshing...' : 'Refresh'}
                    </button>
                </div>

                {/* Stat cards */}
                <div className="hd-stats-grid">
                    <StatCard icon={Users}        label="Total Requests" value={stats.total    ?? 0} accent="#60a5fa" />
                    <StatCard icon={Clock}        label="Pending"        value={stats.pending  ?? 0} accent="#f59e0b" />
                    <StatCard icon={CheckCircle}  label="Accepted"       value={stats.accepted ?? 0} accent="#4ade80" />
                    <StatCard icon={XCircle}      label="Declined"       value={stats.declined ?? 0} accent="#f87171" />
                </div>

                {/* Filter tabs */}
                <div className="hd-filter-row">
                    {['all', 'pending', 'accepted', 'declined'].map(f => (
                        <button key={f} className={`chip ${filter === f ? 'active' : ''}`}
                            onClick={() => setFilter(f)}>
                            {f === 'all' ? `All (${stats.total ?? 0})` : `${STATUS_CONFIG[f]?.label} (${stats[f] ?? 0})`}
                        </button>
                    ))}
                </div>

                {/* Appointments list */}
                {filtered.length === 0 ? (
                    <div className="hd-empty glass-card">
                        <Users size={40} className="text-muted" />
                        <p className="text-muted">
                            {filter === 'pending'
                                ? 'No pending requests right now. Check back later.'
                                : `No ${filter} appointments.`}
                        </p>
                    </div>
                ) : (
                    <div className="hd-appt-list">
                        {filtered.map(a => <AppointmentCard key={a.id} appt={a} />)}
                    </div>
                )}

                {/* Services chip list */}
                <div className="glass-card hd-services-card">
                    <p className="hd-services-title">Your Services</p>
                    <div className="hd-services-chips">
                        {helper?.services?.map(s => (
                            <span key={s} className="badge badge-muted">{s}</span>
                        ))}
                    </div>
                </div>

                <div style={{ height: 40 }} />
            </main>
        </div>
    )
}
