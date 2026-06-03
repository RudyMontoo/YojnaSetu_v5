import { useState } from 'react'
import { Search, CheckCircle, Clock, Circle, ArrowRight, RefreshCw } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './StatusPage.css'

const ACTIVE_APP = {
    name: 'PM Awas Yojana',
    id: 'APP-2024-8812',
    message: 'Your 2nd installment for housing is being processed!', 
    stages: [
        { name: 'Registered', done: true, amount: null },
        { name: 'Aadhaar Verified', done: true, amount: null },
        { name: '1st Installment', done: true, amount: '₹60,000' },
        { name: 'Construction', done: true, amount: null },
        { name: '2nd Installment', done: false, amount: '₹70,000' },
    ]
}

const PAST_APPS = [
    { name: 'PM Kisan Samman Nidhi', id: '992834771', status: 'active', last: '6th Installment Received ✅' },
    { name: 'Ladli Behna Yojana', id: 'MP-002198', status: 'pending', last: 'Pending ID Verification' },
]

export default function StatusPage() {
    const [loading, setLoading] = useState(false)
    const [appId, setAppId] = useState('')

    const handleFetch = () => {
        setLoading(true)
        setTimeout(() => setLoading(false), 2000)
    }

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="status-header">
                    <h1 className="status-title">Meri Applications</h1>
                    <span className="badge badge-green">
                        <span className="status-dot active" /> Live government portal sync
                    </span>
                </div>

                {/* Search by ID */}
                <div className="glass-card status-search-card">
                    <p className="status-search-label">Check by Application ID or Aadhaar number:</p>
                    <div className="status-search-row">
                        <input
                            className="input-glass"
                            placeholder="e.g. APP-2024-XXXX or Aadhaar No."
                            value={appId}
                            onChange={e => setAppId(e.target.value)}
                        />
                        <button className="btn btn-primary" onClick={handleFetch} disabled={loading}>
                            {loading ? <RefreshCw size={16} className="spin" /> : <><Search size={16} /> Check</>}
                        </button>
                    </div>
                </div>

                {/* Active Application */}
                <div className="glass-card glass-card-glow status-active-card">
                    <div className="status-active-header">
                        <div>
                            <div className="badge badge-saffron" style={{ marginBottom: 8 }}>🔔 Active</div>
                            <h2 className="status-scheme-name">{ACTIVE_APP.name}</h2>
                            <p className="text-muted" style={{ fontSize: 12 }}>ID: {ACTIVE_APP.id}</p>
                        </div>
                        <RefreshCw size={18} className="text-muted" style={{ cursor: 'pointer' }} />
                    </div>

                    <div className="status-alert">
                        <span>🏠</span>
                        <p>{ACTIVE_APP.message}</p>
                    </div>

                    {/* Timeline */}
                    <div className="timeline" style={{ marginTop: 20 }}>
                        {ACTIVE_APP.stages.map((stage, i) => {
                            const isPending = !stage.done && (i === 0 || ACTIVE_APP.stages[i - 1].done)
                            const dotClass = stage.done ? 'done' : isPending ? 'pending' : 'future'
                            const Icon = stage.done ? CheckCircle : isPending ? Clock : Circle
                            return (
                                <div key={i} className={`timeline-item ${stage.done ? 'done' : ''}`}>
                                    <div className={`timeline-dot ${dotClass}`}>
                                        <Icon size={14} />
                                    </div>
                                    <div className="timeline-content">
                                        <p className="timeline-title">{stage.name}
                                            {stage.amount && <span className="text-saffron" style={{ marginLeft: 8, fontSize: 13 }}>{stage.amount}</span>}
                                        </p>
                                        <p className="timeline-sub">{stage.done ? 'Completed ✓' : isPending ? 'Processing...' : 'Upcoming'}</p>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>

                {/* Past Applications */}
                <h2 className="status-section-title">Pichli Applications</h2>
                <div className="status-past-list">
                    {PAST_APPS.map((app, i) => (
                        <div key={i} className="glass-card status-past-card">
                            <div className="status-past-info">
                                <p className="status-past-name">{app.name}</p>
                                <p className="text-muted" style={{ fontSize: 12 }}>ID: {app.id}</p>
                            </div>
                            <div className="status-past-right">
                                <span className={`badge badge-${app.status === 'active' ? 'green' : 'gold'}`}>
                                    {app.status === 'active' ? 'Active' : 'Pending'}
                                </span>
                                <p className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>{app.last}</p>
                            </div>
                            <ArrowRight size={16} className="text-subtle" />
                        </div>
                    ))}
                </div>

                <p className="status-sync-note text-subtle">
                    <RefreshCw size={12} /> Fetching data from Government portal…
                </p>

            </main>
            <BottomNav />
        </div>
    )
}
