import { useState } from 'react'
import { MapPin, Navigation, AlertTriangle, Info } from 'lucide-react'
import { PublicPage } from '../../components/PublicShell'
import { gateway } from '../../lib/api'
import { useAutoTranslate } from '../../lib/i18n'
import './PublicPages.css'

/**
 * Bank-branch locator for NSFDC Channel Partners — carried over from the old
 * CreditSchemesPage's Locator tab when that page was replaced.
 *
 * Note this is NOT the same thing as /csc-finder: that one lists registered
 * CSC kendras (gateway.kendrasNearby), this one finds real bank branches that
 * can actually process a credit application (gateway.creditPartnersNearby,
 * backed by OpenStreetMap server-side). Conflating them would send a citizen
 * to the wrong counter.
 */
const UI = {
    title: 'Find a Channel Partner branch',
    sub: 'Bank branches near you where you can enquire about NSFDC credit and education loans.',
    desc: 'This uses your real location and live OpenStreetMap data to find actual bank branches nearby. Your location is used for this search only and is not stored.',
    find: 'Find branches near me',
    gettingLocation: 'Getting your location…',
    findingBanks: 'Finding nearby banks…',
    showingNear: 'Showing banks near',
    yourLocation: 'your location',
    denied: "Location access was blocked. Allow it in your browser's location settings and try again — this search needs your real location to find real nearby branches.",
    lookupError: "Couldn't reach the branch lookup right now. Please try again in a moment.",
    noBranches: 'No bank branches found within range. Try again from somewhere closer to a town or city centre.',
    kmAway: 'km away',
    directions: 'Directions',
    npa: 'Fund-utilisation and NPA data for Channel Partners is not published by any public source, so this shows real branch locations rather than inventing a ranking a citizen could wrongly rely on. Confirm with the branch that they handle NSFDC schemes before travelling.',
}

export default function PartnerLocatorPage() {
    const [locStatus, setLocStatus] = useState('idle')   // idle | enabling | denied
    const [loadStatus, setLoadStatus] = useState('idle') // idle | loading | done | error
    const [partners, setPartners] = useState([])
    const [note, setNote] = useState('')
    const [locationLabel, setLocationLabel] = useState('')

    const tr = useAutoTranslate([...Object.values(UI), note, locationLabel].filter(Boolean))

    const enableLocation = () => {
        if (!navigator.geolocation) { setLocStatus('denied'); return }
        setLocStatus('enabling')
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                const { latitude: lat, longitude: lng } = pos.coords
                setLocStatus('idle')
                setLoadStatus('loading')
                try {
                    const res = await gateway.creditPartnersNearby(lat, lng)
                    setPartners(res.partners || [])
                    setNote(res.note || '')
                    setLocationLabel(res.locationLabel || '')
                    setLoadStatus('done')
                } catch {
                    setLoadStatus('error')
                }
            },
            () => setLocStatus('denied'),
            { enableHighAccuracy: true, timeout: 10000 },
        )
    }

    const busy = locStatus === 'enabling' || loadStatus === 'loading'

    return (
        <PublicPage tr={tr}>
            <section className="gov-hero" style={{ paddingBottom: 26 }}>
                <div className="gov-container gov-narrow">
                    <h1>{tr(UI.title)}</h1>
                    <p className="gov-hero-sub">{tr(UI.sub)}</p>
                </div>
            </section>

            <section className="gov-section">
                <div className="gov-container gov-narrow">
                    <div className="gov-card" style={{ marginBottom: 16 }}>
                        <p style={{ fontSize: 14, lineHeight: 1.6, marginBottom: 14 }}>{tr(UI.desc)}</p>

                        {loadStatus !== 'done' && (
                            <button className="gov-btn gov-btn-primary" onClick={enableLocation} disabled={busy}>
                                {busy ? <span className="gov-spinner" /> : <MapPin size={17} />}
                                {locStatus === 'enabling' ? tr(UI.gettingLocation)
                                    : loadStatus === 'loading' ? tr(UI.findingBanks)
                                        : tr(UI.find)}
                            </button>
                        )}

                        {loadStatus === 'done' && (
                            <p className="gov-hint" style={{ marginTop: 0 }}>
                                <MapPin size={13} style={{ verticalAlign: '-2px' }} /> {tr(UI.showingNear)}{' '}
                                {(locationLabel && tr(locationLabel)) || tr(UI.yourLocation)}
                            </p>
                        )}

                        {locStatus === 'denied' && (
                            <div className="gov-notice gov-notice-warn" style={{ marginTop: 12 }}>
                                <AlertTriangle size={16} /> <span>{tr(UI.denied)}</span>
                            </div>
                        )}
                        {loadStatus === 'error' && (
                            <div className="gov-notice gov-notice-error" style={{ marginTop: 12 }}>
                                <AlertTriangle size={16} /> <span>{tr(UI.lookupError)}</span>
                            </div>
                        )}
                        {note && (
                            <div className="gov-notice gov-notice-info" style={{ marginTop: 12 }}>
                                <Info size={16} /> <span>{tr(note)}</span>
                            </div>
                        )}
                    </div>

                    {loadStatus === 'done' && partners.length === 0 && (
                        <div className="gov-empty">{tr(UI.noBranches)}</div>
                    )}

                    {partners.map((p) => (
                        <div key={`${p.name}-${p.lat}-${p.lng}`} className="gov-card" style={{ marginBottom: 10 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'baseline' }}>
                                <div>
                                    <strong style={{ color: 'var(--gov-ink)', fontSize: 15 }}>{p.name}</strong>
                                    {p.type && <div className="gov-scheme-code">{p.type}</div>}
                                </div>
                                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                                    {p.distanceKm != null && (
                                        <span className="gov-hint" style={{ marginTop: 0 }}>{p.distanceKm.toFixed(1)} {tr(UI.kmAway)}</span>
                                    )}
                                    <a href={`https://maps.google.com/?q=${p.lat},${p.lng}`} target="_blank" rel="noreferrer"
                                        className="gov-btn gov-btn-ghost gov-btn-sm">
                                        <Navigation size={13} /> {tr(UI.directions)}
                                    </a>
                                </div>
                            </div>
                        </div>
                    ))}

                    <div className="gov-notice gov-notice-warn" style={{ marginTop: 16 }}>
                        <AlertTriangle size={16} /> <span>{tr(UI.npa)}</span>
                    </div>
                </div>
            </section>
        </PublicPage>
    )
}
