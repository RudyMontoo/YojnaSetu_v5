import { useState } from 'react'
import { MapPin, Phone, Clock, Navigation, Star, Headphones, Send, CheckCircle, BadgeCheck } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { gateway } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'
import './CSCFinderPage.css'

const UI = {
    title: 'CSC / Jan Seva Kendra Finder 📍', sub: 'Apne najdeek help centre dhundein',
    mapLoading: 'Map loading… (GPS access required)', enableLoc: 'Enable Location Access',
    locOn: 'Location enabled', openMaps: 'More on Google Maps',
    connectedKendra: 'Connected with us', youHere: 'You are here',
    locDenied: 'Location access blocked — allow it in your browser, or use the list below.',
    nearby: 'Sample Centres', nearYou: 'Centres near you',
    sampleNote: 'Sample list — enable location above to sort by centres nearest you.',
    directions: 'Directions', call: 'Call',
    // callback request
    needHelp: 'Need a person to help you?',
    helpSub: 'Ek CSC helper aapko call karke poori madad karega — form, documents, sab kuch.',
    yourName: 'Aapka naam (optional)', yourPhone: 'Callback number',
    msgPlaceholder: 'Kis scheme / kaam mein madad chahiye? (optional)',
    requestBtn: 'Request a Callback',
    requested: 'Ho gaya! Ek helper jaldi aapko call karega. 📞',
    requestErr: 'Request nahi bhej paaye. Dobara try karein.',
}

const CSC_CENTRES = [
    {
        name: 'Jan Seva Kendra – Peth Naka',
        address: 'Near Gram Panchayat, Peth Naka, Pune – 412101',
        distance: '0.8 km',
        phone: '+91-98765-43210',
        hours: 'Mon–Sat: 9AM – 6PM',
        rating: 4.5,
        connected: true,   // registered through Yojna Sarthi → shows the "connected with us" icon
        services: ['PM-Kisan', 'Aadhaar', 'PAN Card', 'Passport'],
    },
    {
        name: 'Common Service Centre – Chinchwad',
        address: 'Shop No. 4, Mahadeo Nagar, Chinchwad, Pune – 411033',
        distance: '2.3 km',
        phone: '+91-87654-32109',
        hours: 'Mon–Sat: 10AM – 7PM',
        rating: 4.2,
        services: ['Ayushman', 'PMAY', 'Birth Cert.', 'E-Shram'],
    },
    {
        name: 'Gram Panchayat Seva Kendra',
        address: 'Main Road, Talegaon, Pune – 410507',
        distance: '4.1 km',
        phone: '+91-70123-45678',
        hours: 'Mon–Fri: 9AM – 5PM',
        rating: 4.0,
        connected: true,
        services: ['PM-Kisan', 'Ration Card', 'Land Records'],
    },
]

function StarRating({ rating }) {
    return (
        <div className="csc-stars">
            {[1, 2, 3, 4, 5].map(i => (
                <Star key={i} size={12} fill={i <= Math.round(rating) ? '#F59E0B' : 'none'} stroke="#F59E0B" />
            ))}
            <span className="csc-rating-text">{rating}</span>
        </div>
    )
}

export default function CSCFinderPage() {
    const [locStatus, setLocStatus] = useState('idle')   // idle | enabling | on | denied
    const [coords, setCoords] = useState(null)
    const [realKendras, setRealKendras] = useState([])   // registered kendras near the user (Option B)
    const savedUser = (() => { try { return JSON.parse(localStorage.getItem('yojna_user') || '{}') } catch { return {} } })()
    const [name, setName] = useState(savedUser.name || '')
    const [phone, setPhone] = useState(savedUser.phone || '')
    const [message, setMessage] = useState('')
    const [sending, setSending] = useState(false)
    const [sent, setSent] = useState(false)
    const [reqError, setReqError] = useState('')

    const tr = useAutoTranslate([
        ...Object.values(UI),
        ...CSC_CENTRES.flatMap(c => [c.name, c.address, c.hours, ...c.services]),
    ])

    const enableLocation = () => {
        if (!navigator.geolocation) { setLocStatus('denied'); return }
        setLocStatus('enabling')
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                const c = { lat: pos.coords.latitude, lng: pos.coords.longitude }
                setCoords(c); setLocStatus('on')
                // pull the kendras we've registered, nearest first
                try { const r = await gateway.kendrasNearby(c.lat, c.lng); setRealKendras(r.kendras || []) } catch { /* none / offline */ }
            },
            () => setLocStatus('denied'),
            { enableHighAccuracy: true, timeout: 10000 },
        )
    }

    // Registered kendras (real, connected) shown first, then the sample centres.
    const realAsCards = realKendras.map(k => ({
        name: k.name, address: k.address || '', phone: k.phone || '',
        distance: k.distanceKm != null ? `${k.distanceKm} km` : '', hours: '',
        rating: null, services: k.services || [], connected: true, lat: k.lat, lng: k.lng,
    }))
    const listCentres = locStatus === 'on'
        ? [...realAsCards, ...[...CSC_CENTRES].sort((a, b) => (b.connected ? 1 : 0) - (a.connected ? 1 : 0))]
        : CSC_CENTRES

    const submitHelp = async (e) => {
        e.preventDefault()
        if (!phone.trim()) { setReqError('Callback number zaroori hai.'); return }
        setReqError(''); setSending(true)
        try {
            await gateway.requestHelp({ phone: phone.trim(), citizenName: name.trim() || null, message: message.trim() || null })
            setSent(true)
        } catch (err) {
            setReqError(err.message || UI.requestErr)
        } finally { setSending(false) }
    }

    const mapsHref = coords
        ? `https://www.google.com/maps/search/CSC+Jan+Seva+Kendra/@${coords.lat},${coords.lng},14z`
        : null

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="csc-header">
                    <h1 className="csc-title">{tr(UI.title)}</h1>
                    <p className="text-muted csc-sub">{tr(UI.sub)}</p>
                </div>

                {/* ── Request a human callback ── */}
                <div className="glass-card csc-help-card" style={{ padding: 18, marginBottom: 16 }}>
                    {sent ? (
                        <div style={{ textAlign: 'center', padding: '8px 0' }}>
                            <CheckCircle size={34} className="text-saffron" />
                            <p style={{ fontWeight: 600, marginTop: 8 }}>{tr(UI.requested)}</p>
                        </div>
                    ) : (
                        <form onSubmit={submitHelp}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                <Headphones size={18} className="text-saffron" />
                                <h2 style={{ margin: 0, fontSize: 16 }}>{tr(UI.needHelp)}</h2>
                            </div>
                            <p className="text-muted" style={{ fontSize: 13, marginTop: 0, marginBottom: 12 }}>{tr(UI.helpSub)}</p>
                            {reqError && <p className="signin-error" style={{ marginBottom: 8 }}>{tr(reqError)}</p>}
                            <input className="input-glass" placeholder={tr(UI.yourName)}
                                   value={name} onChange={e => setName(e.target.value)}
                                   style={{ width: '100%', marginBottom: 8 }} />
                            <input className="input-glass" inputMode="tel" placeholder={tr(UI.yourPhone)}
                                   value={phone} onChange={e => setPhone(e.target.value)}
                                   style={{ width: '100%', marginBottom: 8 }} required />
                            <textarea className="input-glass" placeholder={tr(UI.msgPlaceholder)}
                                      value={message} onChange={e => setMessage(e.target.value)}
                                      rows={2} style={{ width: '100%', marginBottom: 12, resize: 'vertical' }} />
                            <button type="submit" className="btn btn-primary btn-aarti" style={{ width: '100%' }}
                                    disabled={sending || !phone.trim()}>
                                {sending ? <span className="btn-spinner" /> : <><Send size={15} /> {tr(UI.requestBtn)}</>}
                            </button>
                        </form>
                    )}
                </div>

                {/* Map / location (placeholder — same as before) */}
                <div className="glass-card csc-map-card">
                    <div className="csc-map-placeholder">
                        <MapPin size={36} className="text-saffron" />
                        {locStatus === 'on' ? (
                            <>
                                <p className="text-muted csc-map-text">📍 {tr(UI.locOn)}</p>
                                <a href={mapsHref} target="_blank" rel="noreferrer" className="btn btn-primary btn-sm">
                                    <Navigation size={14} /> {tr(UI.openMaps)}
                                </a>
                            </>
                        ) : locStatus === 'denied' ? (
                            <p className="text-muted csc-map-text">{tr(UI.locDenied)}</p>
                        ) : (
                            <>
                                <p className="text-muted csc-map-text">{tr(UI.mapLoading)}</p>
                                <button className="btn btn-primary btn-sm" onClick={enableLocation} disabled={locStatus === 'enabling'}>
                                    {locStatus === 'enabling' ? <span className="btn-spinner" /> : tr(UI.enableLoc)}
                                </button>
                            </>
                        )}
                    </div>
                </div>

                {/* Nearest CSC list */}
                <h2 className="csc-list-title">{locStatus === 'on' ? tr(UI.nearYou) : tr(UI.nearby)} ({listCentres.length})</h2>
                <p className="text-muted" style={{ fontSize: 12, marginTop: -6, marginBottom: 8 }}>{tr(UI.sampleNote)}</p>
                <div className="csc-list">
                    {listCentres.map((csc, i) => (
                        <div key={i} className="glass-card csc-card">
                            <div className="csc-card-top">
                                <div className="csc-icon-wrap">
                                    <MapPin size={20} className="text-saffron" />
                                </div>
                                <div className="csc-info">
                                    <p className="csc-name" style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                                        {tr(csc.name)}
                                        {csc.connected && (
                                            <span className="badge badge-green" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                                                <BadgeCheck size={12} /> {tr(UI.connectedKendra)}
                                            </span>
                                        )}
                                    </p>
                                    {csc.address && <p className="text-muted csc-address">{tr(csc.address)}</p>}
                                    {csc.rating != null && <StarRating rating={csc.rating} />}
                                </div>
                                {csc.distance && (
                                    <div className="csc-distance">
                                        <span className="badge badge-green">{csc.distance}</span>
                                    </div>
                                )}
                            </div>

                            {(csc.phone || csc.hours) && (
                                <div className="csc-details">
                                    {csc.phone && (
                                        <div className="csc-detail-row">
                                            <Phone size={13} className="text-muted" />
                                            <a href={`tel:${csc.phone}`} className="text-muted csc-detail-text">{csc.phone}</a>
                                        </div>
                                    )}
                                    {csc.hours && (
                                        <div className="csc-detail-row">
                                            <Clock size={13} className="text-muted" />
                                            <span className="text-muted csc-detail-text">{tr(csc.hours)}</span>
                                        </div>
                                    )}
                                </div>
                            )}

                            {csc.services?.length > 0 && (
                                <div className="csc-services">
                                    {csc.services.map(s => <span key={s} className="badge badge-muted">{tr(s)}</span>)}
                                </div>
                            )}

                            <div className="csc-actions">
                                <a href={csc.lat != null
                                    ? `https://www.google.com/maps/dir/?api=1&destination=${csc.lat},${csc.lng}`
                                    : `https://maps.google.com?q=${encodeURIComponent(csc.address || csc.name)}`}
                                   target="_blank" rel="noreferrer" className="btn btn-primary btn-sm">
                                    <Navigation size={14} /> {tr(UI.directions)}
                                </a>
                                {csc.phone && (
                                    <a href={`tel:${csc.phone}`} className="btn btn-ghost btn-sm">
                                        <Phone size={14} /> {tr(UI.call)}
                                    </a>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </main>
            <BottomNav />
        </div>
    )
}
