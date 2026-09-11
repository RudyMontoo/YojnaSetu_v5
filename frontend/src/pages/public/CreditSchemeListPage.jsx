import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Users, Info } from 'lucide-react'
import { PublicPage } from '../../components/PublicShell'
import { gateway } from '../../lib/api'
import { formatInr } from '../../lib/emiCalculator'
import { useAutoTranslate } from '../../lib/i18n'
import './PublicPages.css'

const UI = {
    title: 'NSFDC credit & education schemes',
    sub: 'Concessional loans for the SC community. Browse freely — you only need an account when you apply.',
    filterType: 'Type of loan',
    filterCost: 'Your project cost is about',
    all: 'All',
    micro: 'Micro finance',
    term: 'Term loan',
    education: 'Education',
    anyCost: 'Any amount',
    maxLoan: 'Maximum loan',
    rate: 'Interest rate',
    noEmiFor: 'No EMI for the first',
    months: 'months',
    repayIn: 'Repay over up to',
    covers: 'Covers up to',
    ofCost: 'of project cost',
    womenOnly: 'Women applicants only',
    unverified: 'Figures not independently verified',
    viewDetails: 'View details',
    incomeLimit: 'Family income limit',
    empty: 'No scheme matches these filters. Try widening them.',
    loadError: "Couldn't load schemes right now. Please refresh in a moment.",
    loading: 'Loading schemes…',
    countNote: 'schemes available',
}

const COST_BANDS = [
    { key: 'any', label: UI.anyCost, max: null },
    { key: 'u140', label: 'Up to ₹1.4 lakh', max: 140000 },
    { key: 'u5l', label: 'Up to ₹5 lakh', max: 500000 },
    { key: 'u50l', label: 'Up to ₹50 lakh', max: 5000000 },
]

export default function CreditSchemeListPage() {
    const [products, setProducts] = useState(null)
    const [failed, setFailed] = useState(false)
    const [type, setType] = useState('all')
    const [band, setBand] = useState('any')

    useEffect(() => {
        gateway.creditProducts()
            .then((list) => setProducts(Array.isArray(list) ? list : []))
            .catch(() => setFailed(true))
    }, [])

    const filtered = useMemo(() => {
        if (!products) return []
        const maxCost = COST_BANDS.find((b) => b.key === band)?.max
        return products.filter((p) => {
            if (type !== 'all' && p.type !== type) return false
            if (maxCost != null) {
                // A scheme is relevant if it can finance a project of this size:
                // its own floor must not be above the citizen's budget.
                if (p.unitCostFloor && p.unitCostFloor > maxCost) return false
            }
            return true
        })
    }, [products, type, band])

    const tr = useAutoTranslate([
        ...Object.values(UI),
        ...COST_BANDS.map((b) => b.label),
        ...(products || []).flatMap((p) => [p.name, p.description]),
    ])

    return (
        <PublicPage tr={tr}>
            <section className="gov-hero" style={{ paddingBottom: 28 }}>
                <div className="gov-container">
                    <h1>{tr(UI.title)}</h1>
                    <p className="gov-hero-sub">{tr(UI.sub)}</p>
                </div>
            </section>

            <section className="gov-section">
                <div className="gov-container">
                    <div className="gov-filters">
                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.filterType)}</span>
                            <select className="gov-select" value={type} onChange={(e) => setType(e.target.value)}>
                                <option value="all">{tr(UI.all)}</option>
                                <option value="micro">{tr(UI.micro)}</option>
                                <option value="term">{tr(UI.term)}</option>
                                <option value="education">{tr(UI.education)}</option>
                            </select>
                        </label>
                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.filterCost)}</span>
                            <select className="gov-select" value={band} onChange={(e) => setBand(e.target.value)}>
                                {COST_BANDS.map((b) => (
                                    <option key={b.key} value={b.key}>{tr(b.label)}</option>
                                ))}
                            </select>
                        </label>
                    </div>

                    {failed && <div className="gov-notice gov-notice-error">{tr(UI.loadError)}</div>}
                    {!failed && products === null && <div className="gov-empty">{tr(UI.loading)}</div>}
                    {!failed && products !== null && filtered.length === 0 && (
                        <div className="gov-empty">{tr(UI.empty)}</div>
                    )}

                    {filtered.length > 0 && (
                        <>
                            <p className="gov-section-sub">{filtered.length} {tr(UI.countNote)}</p>
                            <div className="gov-grid">
                                {filtered.map((p) => (
                                    <div key={p.id} className="gov-card gov-scheme-card">
                                        <div>
                                            <span className="gov-scheme-code">{p.code}</span>
                                            <h3>{tr(p.name)}</h3>
                                        </div>

                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                            {p.womenOnly && (
                                                <span className="gov-badge gov-badge-muted">
                                                    <Users size={11} /> {tr(UI.womenOnly)}
                                                </span>
                                            )}
                                            {p.figuresVerified === false && (
                                                <span className="gov-badge gov-badge-warn">
                                                    <Info size={11} /> {tr(UI.unverified)}
                                                </span>
                                            )}
                                        </div>

                                        <p className="gov-scheme-desc">{tr(p.description)}</p>

                                        <div className="gov-facts">
                                            <div>
                                                <div className="gov-fact-label">{tr(UI.maxLoan)}</div>
                                                <div className="gov-fact-value">{formatInr(p.maxLoanAmount)}</div>
                                            </div>
                                            <div>
                                                <div className="gov-fact-label">{tr(UI.rate)}</div>
                                                <div className="gov-fact-value">{p.interestRate}%</div>
                                            </div>
                                        </div>

                                        <p className="gov-hint">
                                            {tr(UI.noEmiFor)} {p.moratoriumMonths} {tr(UI.months)} · {tr(UI.repayIn)}{' '}
                                            {p.maxTenureMonths} {tr(UI.months)}
                                        </p>

                                        <Link to={`/credit-schemes/${p.id}`} className="gov-btn gov-btn-secondary gov-btn-sm">
                                            {tr(UI.viewDetails)} <ArrowRight size={15} />
                                        </Link>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>
            </section>
        </PublicPage>
    )
}
