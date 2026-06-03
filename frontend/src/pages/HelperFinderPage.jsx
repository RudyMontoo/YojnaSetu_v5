import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
    MapPin, Star, Phone, Languages, Users, CheckCircle,
    Search, UserPlus, Send, X, Loader2, Building2, User
} from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './HelperFinderPage.css'

/* ── Static CSC Centres (always shown) ──────────────────────── */
const CSC_CENTRES = [
    {
        id: 'csc-1', type: 'csc',
        name: 'Jan Seva Kendra – Peth Naka',
        address: 'Near Gram Panchayat, Peth Naka, Pune – 412101',
        phone: '+91-98765-43210',
        hours: 'Mon–Sat: 9AM – 6PM',
        rating: 4.5, total_helped: 340,
        district: 'Pune', state: 'Maharashtra',
        languages: ['Hindi', 'Marathi', 'English'],
        services: ['PM-Kisan', 'Aadhaar', 'PAN Card', 'Passport', 'PMAY'],
    },
    {
        id: 'csc-2', type: 'csc',
        name: 'Common Service Centre – Chinchwad',
        address: 'Shop No. 4, Mahadeo Nagar, Chinchwad, Pune – 411033',
        phone: '+91-87654-32109',
        hours: 'Mon–Sat: 10AM – 7PM',
        rating: 4.2, total_helped: 210,
        district: 'Pune', state: 'Maharashtra',
        languages: ['Marathi', 'Hindi'],
        services: ['Ayushman', 'PMAY', 'Birth Cert.', 'E-Shram'],
    },
]

/* ── Booking Modal ──────────────────────────────────────────── */
function BookingModal({ helper, schemeName, onClose }) {
    const [form, setForm] = useState({ name: '', phone: '', email: '', message: '' })
    const [loading, setLoading] = useState(false)
    const [done, setDone] = useState(null)  // null | { appointment_id, message }
    const [error, setError] = useState('')

    const update = (k, v) => setForm(f => ({ ...f, [k]: v }))

    const submit = async () => {
        if (!form.name.trim() || !form.phone.trim()) {
            setError('Name and phone are required.')
            return
        }
        setLoading(true)
        setError('')
        try {
            const res = await fetch('/sahayak/appointments/request', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    helper_id: helper.id,
                    citizen_name: form.name,
                    citizen_phone: form.phone,
                    citizen_email: form.email,
                    scheme_name: schemeName,
                    message: form.message,
                })
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || 'Request failed')
            setDone(data)
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="booking-overlay" onClick={onClose}>
            <div className="booking-card glass-card" onClick={e => e.stopPropagation()}>
                <div className="booking-header">
                    <div>
                        <p className="booking-eyebrow">Request Assistance</p>
                        <h3 className="booking-title">{helper.name}</h3>
                        {schemeName && <p className="booking-scheme">For: <strong>{schemeName}</strong></p>}
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={18} /></button>
                </div>

                {done ? (
                    <div className="booking-success">
                        <CheckCircle size={40} className="text-green" />
                        <h4>Request Sent!</h4>
                        <p>{done.message}</p>
                        <p className="text-subtle" style={{ fontSize: 12 }}>
                            You'll be notified when {helper.name} responds. Keep your phone available.
                        </p>
                        <button className="btn btn-primary btn-sm" onClick={onClose} style={{ marginTop: 8 }}>Done</button>
                    </div>
                ) : (
                    <div className="booking-form">
                        <div className="booking-field">
                            <label className="field-label">Your Name *</label>
                            <input className="input-glass" placeholder="e.g. Ramesh Kumar"
                                value={form.name} onChange={e => update('name', e.target.value)} />
                        </div>
                        <div className="booking-field">
                            <label className="field-label">Phone Number *</label>
                            <input className="input-glass" placeholder="+91-XXXXX-XXXXX" type="tel"
                                value={form.phone} onChange={e => update('phone', e.target.value)} />
                        </div>
                        <div className="booking-field">
                            <label className="field-label">Email (optional — for confirmation)</label>
                            <input className="input-glass" placeholder="your@email.com" type="email"
                                value={form.email} onChange={e => update('email', e.target.value)} />
                        </div>
                        <div className="booking-field">
                            <label className="field-label">Message to helper (optional)</label>
                            <textarea className="input-glass booking-textarea"
                                placeholder="e.g. I need help gathering documents for PMAY..."
                                value={form.message} onChange={e => update('message', e.target.value)} rows={3} />
                        </div>
                        {error && <p className="booking-error">{error}</p>}
                        <button className="btn btn-primary booking-submit-btn" onClick={submit} disabled={loading}>
                            {loading ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
                            {loading ? 'Sending...' : 'Send Request'}
                        </button>
                    </div>
                )}
            </div>
        </div>
    )
}

/* ── Helper Card ─────────────────────────────────────────────── */
function HelperCard({ helper, onBook, type }) {
    return (
        <div className={`helper-card glass-card ${type}`}>
            <div className="helper-card-top">
                <div className={`helper-avatar ${type}`}>
                    {type === 'csc' ? <Building2 size={22} /> : <User size={22} />}
                </div>
                <div className="helper-info">
                    <div className="helper-name-row">
                        <span className="helper-name">{helper.name}</span>
                        {type === 'csc' && (
                            <span className="helper-type-badge csc">CSC</span>
                        )}
                        {type === 'volunteer' && (
                            <span className="helper-type-badge volunteer">Volunteer</span>
                        )}
                    </div>
                    <div className="helper-location">
                        <MapPin size={11} /> {helper.district}, {helper.state}
                    </div>
                    <div className="helper-rating-row">
                        {[1,2,3,4,5].map(i => (
                            <Star key={i} size={11}
                                fill={i <= Math.round(helper.rating) ? '#F59E0B' : 'none'}
                                stroke="#F59E0B" />
                        ))}
                        <span className="helper-rating-text">{helper.rating}</span>
                        <span className="helper-helped">{helper.total_helped}+ helped</span>
                    </div>
                </div>
            </div>

            {type === 'csc' && helper.hours && (
                <p className="helper-hours">🕐 {helper.hours}</p>
            )}
            {type === 'volunteer' && helper.bio && (
                <p className="helper-bio">{helper.bio}</p>
            )}

            <div className="helper-langs">
                <Languages size={12} className="text-subtle" />
                {(helper.languages || []).map(l => (
                    <span key={l} className="badge badge-muted" style={{ fontSize: 11 }}>{l}</span>
                ))}
            </div>

            <div className="helper-services">
                {(helper.services || []).slice(0, 4).map(s => (
                    <span key={s} className="badge badge-muted helper-service-badge">{s}</span>
                ))}
                {(helper.services || []).length > 4 && (
                    <span className="badge badge-muted">+{helper.services.length - 4}</span>
                )}
            </div>

            <div className="helper-card-footer">
                {type === 'csc' && helper.phone ? (
                    <a href={`tel:${helper.phone}`} className="btn btn-ghost btn-sm helper-call-btn">
                        <Phone size={13} /> Call Centre
                    </a>
                ) : null}
                <button className="btn btn-primary btn-sm helper-book-btn" onClick={() => onBook(helper)}>
                    <Send size={13} /> Request Help
                </button>
            </div>
        </div>
    )
}

/* ── Main Page ───────────────────────────────────────────────── */
export default function HelperFinderPage() {
    const [searchParams] = useSearchParams()
    const navigate = useNavigate()
    const schemeName = searchParams.get('scheme') || ''

    const [tab, setTab] = useState('all')  // all | csc | volunteer
    const [search, setSearch] = useState('')
    const [volunteers, setVolunteers] = useState([])
    const [loading, setLoading] = useState(true)
    const [bookingHelper, setBookingHelper] = useState(null)

    useEffect(() => {
        fetch('/sahayak/helpers')
            .then(r => r.json())
            .then(d => setVolunteers(d.helpers || []))
            .catch(() => setVolunteers([]))
            .finally(() => setLoading(false))
    }, [])

    const allHelpers = [
        ...CSC_CENTRES.map(c => ({ ...c, type: 'csc' })),
        ...volunteers.map(v => ({ ...v, type: 'volunteer' }))
    ]

    const filtered = allHelpers.filter(h => {
        const matchTab = tab === 'all' || h.type === tab || (tab === 'csc' && h.type === 'csc') || (tab === 'volunteer' && h.type === 'volunteer')
        const q = search.toLowerCase()
        const matchSearch = !q ||
            h.name.toLowerCase().includes(q) ||
            h.district.toLowerCase().includes(q) ||
            h.state.toLowerCase().includes(q) ||
            (h.services || []).some(s => s.toLowerCase().includes(q))
        return matchTab && matchSearch
    })

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                {/* Header */}
                <div className="helper-page-header">
                    {schemeName && (
                        <div className="helper-scheme-banner">
                            <CheckCircle size={14} className="text-saffron" />
                            Finding helpers for: <strong>{schemeName}</strong>
                        </div>
                    )}
                    <h1 className="helper-page-title">
                        Jan Sahayak <span className="text-saffron">Connect</span>
                    </h1>
                    <p className="text-muted helper-page-sub">
                        Find a CSC centre or trusted volunteer to help you apply for government schemes in person.
                    </p>
                </div>

                {/* Register CTA */}
                <div className="helper-register-cta glass-card">
                    <div className="helper-register-text">
                        <UserPlus size={18} className="text-saffron" />
                        <div>
                            <p className="helper-register-title">Want to help your community?</p>
                            <p className="text-subtle" style={{ fontSize: 12 }}>Register as a Jan Sahayak volunteer</p>
                        </div>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={() => navigate('/register-helper')}>
                        Register →
                    </button>
                </div>

                {/* Search */}
                <div className="helper-search-row">
                    <Search size={16} className="helper-search-icon text-muted" />
                    <input
                        className="input-glass helper-search-input"
                        placeholder="Search by name, district, or scheme..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>

                {/* Tabs */}
                <div className="helper-tabs">
                    {[
                        { key: 'all', label: `All (${allHelpers.length})` },
                        { key: 'csc', label: `CSC Centres (${CSC_CENTRES.length})` },
                        { key: 'volunteer', label: `Volunteers (${volunteers.length})` },
                    ].map(t => (
                        <button
                            key={t.key}
                            className={`chip ${tab === t.key ? 'active' : ''}`}
                            onClick={() => setTab(t.key)}
                        >
                            {t.label}
                        </button>
                    ))}
                </div>

                {/* List */}
                {loading ? (
                    <div className="helper-loading">
                        <Loader2 size={28} className="text-saffron spin" />
                        <p className="text-muted">Loading helpers...</p>
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="helper-empty glass-card">
                        <Users size={36} className="text-muted" />
                        <p className="text-muted">No helpers found.</p>
                        <button className="btn btn-primary btn-sm" onClick={() => navigate('/register-helper')}>
                            Be the first volunteer →
                        </button>
                    </div>
                ) : (
                    <div className="helper-grid">
                        {filtered.map(h => (
                            <HelperCard
                                key={h.id}
                                helper={h}
                                type={h.type}
                                onBook={setBookingHelper}
                            />
                        ))}
                    </div>
                )}

                <div style={{ height: 80 }} />
            </main>

            {bookingHelper && (
                <BookingModal
                    helper={bookingHelper}
                    schemeName={schemeName}
                    onClose={() => setBookingHelper(null)}
                />
            )}

            <BottomNav />
        </div>
    )
}
