import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Bookmark, BookmarkCheck, Loader2 } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { gateway } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'
import './SchemesPage.css'

// Static labels on this page — live-translated (not hand-registered) so the
// whole catalogue reads in the chosen language, scheme content included.
const UI = {
    title: 'Yojana Catalogue', schemes: 'Central & State schemes',
    searchPh: 'Scheme name ya ministry dhunden…', found: 'schemes found',
    showing: 'showing', loadMore: 'Load more', remaining: 'remaining',
    janiye: 'Janiye →', loginNote: 'Please login to browse the full catalogue.',
    empty: 'Koi scheme nahi mila. Dusra search try karein.', central: 'Central',
}

// v5.0 (2026-07-07): real catalogue from GET /api/v2/schemes — previously
// this page rendered a hardcoded 8-scheme demo list while Mongo held
// 1,900+ real schemes. Chips map to the DB's own sector taxonomy
// (contains-matched server-side); Pension searches names instead because
// pension schemes live under "Social welfare" sectors, not a pension sector.
const CATEGORY_FILTERS = [
    { label: 'All' },
    { label: 'Agriculture', sector: 'agri' },
    { label: 'Housing', sector: 'hous' },
    { label: 'Health', sector: 'health' },
    { label: 'Education', sector: 'education' },
    { label: 'Women', sector: 'women' },
    { label: 'Skill Dev', sector: 'skill,employment' },
    { label: 'Pension', search: 'pension' },
    { label: 'Business', sector: 'business,banking,entrepreneur' },
]

export default function SchemesPage() {
    const navigate = useNavigate()
    const [activeCat, setActiveCat] = useState('All')
    const [search, setSearch] = useState('')
    const [savedIds, setSavedIds] = useState(new Set())
    const [schemes, setSchemes] = useState([])
    const [total, setTotal] = useState(null)
    const [page, setPage] = useState(0)
    const [hasMore, setHasMore] = useState(false)
    const [loading, setLoading] = useState(true)
    const [note, setNote] = useState('')
    const debounceRef = useRef(null)

    // Live-translate every visible string: page labels, chip labels, and the
    // dynamic scheme names/benefits/sectors. English → no-op; other langs hit
    // the cached /translate endpoint.
    const tr = useAutoTranslate([
        ...Object.values(UI),
        ...CATEGORY_FILTERS.map(c => c.label),
        ...schemes.flatMap(s => [s.name, s.benefitAmount, (s.sector || '').split(',')[0]].filter(Boolean)),
    ])

    const fetchSchemes = async (pageNum, append = false) => {
        setLoading(true)
        try {
            const cat = CATEGORY_FILTERS.find(c => c.label === activeCat) || {}
            const data = await gateway.listSchemes({
                // typed search wins; the Pension chip's keyword fills in only when the box is empty
                search: search.trim() || cat.search || undefined,
                sector: cat.sector || undefined,
                page: pageNum,
                size: 24,
            })
            setSchemes(prev => append ? [...prev, ...data.schemes] : data.schemes)
            setTotal(data.total)
            setHasMore(data.has_more)
            setPage(data.page)
            setNote('')
        } catch (err) {
            if (!append) setSchemes([])
            setNote(err.status === 401 || err.status === 403
                ? 'Please login to browse the full catalogue.'
                : `Could not load schemes: ${err.message}`)
        } finally {
            setLoading(false)
        }
    }

    // refetch on filter change; debounce while typing
    useEffect(() => {
        clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(() => fetchSchemes(0), search ? 300 : 0)
        return () => clearTimeout(debounceRef.current)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [search, activeCat])

    useEffect(() => {
        const localSaved = (() => { try { return JSON.parse(localStorage.getItem('yojna_saved') || '[]') } catch { return [] } })()
        // eslint-disable-next-line react-hooks/set-state-in-effect
        if (localSaved.length > 0) setSavedIds(new Set(localSaved.map(r => r.scheme_id)))
    }, [])

    const toggleSave = (e, scheme) => {
        e.stopPropagation()
        const localSaved = (() => { try { return JSON.parse(localStorage.getItem('yojna_saved') || '[]') } catch { return [] } })()
        let updated
        if (savedIds.has(scheme.schemeCode)) {
            updated = localSaved.filter(x => x.scheme_id !== scheme.schemeCode)
            setSavedIds(s => { const n = new Set(s); n.delete(scheme.schemeCode); return n })
        } else {
            updated = [...localSaved, { scheme_id: scheme.schemeCode, scheme_name: scheme.name }]
            setSavedIds(s => new Set([...s, scheme.schemeCode]))
        }
        localStorage.setItem('yojna_saved', JSON.stringify(updated))
    }

    const openScheme = (s) => {
        // SchemeDetailPage renders route state for real schemes (same keys
        // ChatPage passes): name/benefit/apply_url/sector/state
        navigate(`/schemes/${s.schemeCode}`, {
            state: {
                name: s.name,
                benefit: s.benefitAmount,
                apply_url: s.applyUrl,
                sector: s.sector,
                state: s.state || 'Central',
            },
        })
    }

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="schemes-header">
                    <h1 className="schemes-title font-display">{tr(UI.title)}</h1>
                    <p className="text-muted schemes-sub">
                        {total !== null ? `${total.toLocaleString('en-IN')} ${tr(UI.schemes)}` : tr(UI.schemes)}
                    </p>
                </div>

                {/* Search */}
                <div className="schemes-search glass-card">
                    <Search size={18} className="text-subtle" />
                    <input
                        className="schemes-search-input"
                        placeholder={tr(UI.searchPh)}
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                    {search && <button className="schemes-clear" onClick={() => setSearch('')}>✕</button>}
                </div>

                {/* Category Filters */}
                <div className="schemes-filters">
                    {CATEGORY_FILTERS.map(cat => (
                        <button
                            key={cat.label}
                            className={`chip ${activeCat === cat.label ? 'active' : ''}`}
                            onClick={() => setActiveCat(cat.label)}
                        >
                            {tr(cat.label)}
                        </button>
                    ))}
                </div>

                {note && (
                    <div className="glass-card" style={{ padding: 14, marginBottom: 14, fontSize: 13.5 }}>{tr(note)}</div>
                )}

                {/* Results count */}
                {total !== null && !note && (
                    <p className="schemes-count text-muted">
                        {total.toLocaleString('en-IN')} {tr(UI.found)}
                        {schemes.length < total ? ` · ${tr(UI.showing)} ${schemes.length}` : ''}
                    </p>
                )}

                {/* Grid */}
                <div className="schemes-grid">
                    {schemes.map(scheme => (
                        <div
                            key={scheme.schemeCode}
                            className="glass-card scheme-card schemes-item"
                            onClick={() => openScheme(scheme)}
                        >
                            <div className="scheme-card-header">
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                                        {scheme.sector && <span className="badge badge-saffron">{tr(String(scheme.sector).split(',')[0])}</span>}
                                        <span className="badge badge-muted">{tr(scheme.state || UI.central)}</span>
                                    </div>
                                    <div className="scheme-card-title">{tr(scheme.name)}</div>
                                </div>
                                <button
                                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                                    onClick={(e) => toggleSave(e, scheme)}
                                    title={savedIds.has(scheme.schemeCode) ? 'Remove bookmark' : 'Save scheme'}
                                >
                                    {savedIds.has(scheme.schemeCode)
                                        ? <BookmarkCheck size={18} color="var(--saffron)" />
                                        : <Bookmark size={18} className="text-subtle" />}
                                </button>
                            </div>
                            {scheme.benefitAmount && <p className="scheme-card-benefit">{tr(scheme.benefitAmount)}</p>}
                            <div className="scheme-card-footer">
                                <button className="btn btn-saffron-outline btn-sm" onClick={e => { e.stopPropagation(); openScheme(scheme) }}>
                                    {tr(UI.janiye)}
                                </button>
                            </div>
                        </div>
                    ))}
                </div>

                {loading && (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
                        <Loader2 size={22} className="spin text-saffron" />
                    </div>
                )}

                {!loading && hasMore && (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0 24px' }}>
                        <button className="btn btn-saffron-outline" onClick={() => fetchSchemes(page + 1, true)}>
                            {tr(UI.loadMore)} ({(total - schemes.length).toLocaleString('en-IN')} {tr(UI.remaining)})
                        </button>
                    </div>
                )}

                {!loading && schemes.length === 0 && !note && (
                    <div className="schemes-empty">
                        <span>🔍</span>
                        <p>{tr(UI.empty)}</p>
                    </div>
                )}

            </main>
            <BottomNav />
        </div>
    )
}
