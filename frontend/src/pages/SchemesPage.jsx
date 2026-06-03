import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ChevronRight, Filter, Bookmark, BookmarkCheck } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './SchemesPage.css'

const CATEGORIES = ['All', 'Agriculture', 'Housing', 'Health', 'Education', 'Women', 'Skill Dev', 'Pension', 'Business']

const SCHEMES = [
    { id: 'pm-kisan', name: 'PM-Kisan Samman Nidhi', benefit: '₹6,000 per year directly to farmer bank accounts', category: 'Agriculture', tag: 'Central', eligible: true },
    { id: 'pm-awas', name: 'PM Awas Yojana (Gramin)', benefit: 'Free pucca house for rural BPL families', category: 'Housing', tag: 'Central', eligible: true },
    { id: 'ayushman', name: 'Ayushman Bharat – PMJAY', benefit: '₹5 Lakh health insurance per family per year', category: 'Health', tag: 'Central', eligible: false },
    { id: 'ladli', name: 'Ladli Behna Yojana', benefit: '₹1,250/month for women of Madhya Pradesh', category: 'Women', tag: 'State', eligible: true },
    { id: 'kcc', name: 'Kisan Credit Card', benefit: 'Low-interest short-term crop loans', category: 'Agriculture', tag: 'Central', eligible: false },
    { id: 'mudra', name: 'PM Mudra Yojana', benefit: 'Loans upto ₹10 Lakh for micro-enterprises', category: 'Business', tag: 'Central', eligible: true },
    { id: 'scholarship', 'name': 'NSP National Scholarship', benefit: 'Merit & means based scholarships for students', category: 'Education', tag: 'Central', eligible: false },
    { id: 'nps', name: 'Atal Pension Yojana', benefit: 'Guaranteed pension of ₹1000–5000/month', category: 'Pension', tag: 'Central', eligible: true },
]

export default function SchemesPage() {
    const navigate = useNavigate()
    const [activeCat, setActiveCat] = useState('All')
    const [search, setSearch] = useState('')
    const [savedIds, setSavedIds] = useState(new Set())

    const loadSaved = async () => {
        // Load from localStorage first
        const localSaved = (() => { try { return JSON.parse(localStorage.getItem('yojna_saved') || '[]') } catch { return [] } })()
        if (localSaved.length > 0) setSavedIds(new Set(localSaved.map(r => r.scheme_id)))
    }

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        loadSaved()
    }, [])

    const toggleSave = async (e, scheme) => {
        e.stopPropagation()
        const localSaved = (() => { try { return JSON.parse(localStorage.getItem('yojna_saved') || '[]') } catch { return [] } })()
        let updated
        if (savedIds.has(scheme.id)) {
            updated = localSaved.filter(x => x.scheme_id !== scheme.id)
            setSavedIds(s => { const n = new Set(s); n.delete(scheme.id); return n })
        } else {
            updated = [...localSaved, { scheme_id: scheme.id, scheme_name: scheme.name }]
            setSavedIds(s => new Set([...s, scheme.id]))
        }
        localStorage.setItem('yojna_saved', JSON.stringify(updated))
    }

    const filtered = SCHEMES.filter(s => {
        const matchCat = activeCat === 'All' || s.category === activeCat
        const matchSearch = !search || s.name.toLowerCase().includes(search.toLowerCase()) || s.benefit.toLowerCase().includes(search.toLowerCase())
        return matchCat && matchSearch
    })

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="schemes-header">
                    <h1 className="schemes-title">Yojana Catalogue</h1>
                    <p className="text-muted schemes-sub">419+ Central & State schemes</p>
                </div>

                {/* Search */}
                <div className="schemes-search glass-card">
                    <Search size={18} className="text-subtle" />
                    <input
                        className="schemes-search-input"
                        placeholder="Scheme name ya benefit dhunden…"
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                    {search && <button className="schemes-clear" onClick={() => setSearch('')}>✕</button>}
                </div>

                {/* Category Filters */}
                <div className="schemes-filters">
                    {CATEGORIES.map(cat => (
                        <button
                            key={cat}
                            className={`chip ${activeCat === cat ? 'active' : ''}`}
                            onClick={() => setActiveCat(cat)}
                        >
                            {cat}
                        </button>
                    ))}
                </div>

                {/* Results count */}
                <p className="schemes-count text-muted">{filtered.length} scheme{filtered.length !== 1 ? 's' : ''} found</p>

                {/* Grid */}
                <div className="schemes-grid">
                    {filtered.map(scheme => (
                        <div
                            key={scheme.id}
                            className="glass-card scheme-card schemes-item"
                            onClick={() => navigate(`/schemes/${scheme.id}`)}
                        >
                            <div className="scheme-card-header">
                                <div style={{ flex: 1 }}>
                                    <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                                        <span className="badge badge-saffron">{scheme.category}</span>
                                        <span className="badge badge-muted">{scheme.tag}</span>
                                        {scheme.eligible && <span className="badge badge-green">✓ Eligible</span>}
                                    </div>
                                    <div className="scheme-card-title">{scheme.name}</div>
                                </div>
                                <button
                                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
                                    onClick={(e) => toggleSave(e, scheme)}
                                    title={savedIds.has(scheme.id) ? 'Remove bookmark' : 'Save scheme'}
                                >
                                    {savedIds.has(scheme.id)
                                        ? <BookmarkCheck size={18} color="var(--saffron)" />
                                        : <Bookmark size={18} className="text-subtle" />}
                                </button>
                            </div>
                            <p className="scheme-card-benefit">{scheme.benefit}</p>
                            <div className="scheme-card-footer">
                                <button className="btn btn-saffron-outline btn-sm" onClick={e => { e.stopPropagation(); navigate(`/schemes/${scheme.id}`) }}>
                                    Janiye →
                                </button>
                            </div>
                        </div>
                    ))}
                </div>

                {filtered.length === 0 && (
                    <div className="schemes-empty">
                        <span>🔍</span>
                        <p>Koi scheme nahi mila. Dusra search try karein.</p>
                    </div>
                )}

            </main>
            <BottomNav />
        </div>
    )
}
