import { useState, useMemo } from 'react'
import { Landmark, Calculator, MapPin, IndianRupee, GraduationCap, Info, Navigation, AlertTriangle } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { recommendScheme, NSFDC_SCHEMES, INCOME_CEILING } from '../lib/nsfdcSchemes'
import { calculateEmi, formatInr } from '../lib/emiCalculator'
import { gateway } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'
import './CreditSchemesPage.css'

// Static labels — live-translated (not hand-registered), same pattern as
// SchemesPage.jsx/StatusPage.jsx, so the whole module reads in the chosen
// language. Built for SIH PS 26092 (AI-Driven Scheme Matching for
// Marginalized Entrepreneurs, Ministry of Social Justice & Empowerment) —
// this page previously skipped i18n entirely (built fast, in isolation).
const UI = {
    psTag: 'SIH PS 26092 · AI-Driven Scheme Matching for Marginalized Entrepreneurs',
    title: 'NSFDC Credit & Education Loans',
    subtitle: 'Concessional financing for the SC community',
    tabRecommend: 'Scheme Recommender', tabCalculator: 'EMI Calculator', tabLocator: 'Partner Locator',
    // Recommender
    forWhat: 'What is this for?', business: 'Business / self-employment project',
    education: 'Education (course, tuition, hostel)', projectCost: 'Estimated project cost (₹)',
    projectCostPh: 'e.g. 80000', income: 'Annual family income (₹)', incomePh: 'e.g. 300000',
    recommendBtn: 'Recommend a Scheme', maxLoan: 'Max loan', interestRate: 'Interest rate',
    moratorium: 'Moratorium', coverage: 'Coverage', months: 'months', upTo: 'up to',
    // Calculator
    scheme: 'Scheme', loanAmount: 'Loan amount (max', repayTenure: 'Repayment tenure in months (max',
    monthlyEmi: 'Monthly EMI', totalInterest: 'Total interest', totalPayment: 'Total payment',
    viewSchedule: 'View month-by-month repayment schedule',
    colMonth: 'Month', colEmi: 'EMI', colPrincipal: 'Principal', colInterest: 'Interest', colBalance: 'Balance',
    // Locator
    locatorTitle: 'Partner Locator',
    locatorDesc: 'Finds real bank branches near your current location using OpenStreetMap data, to help you find a Channel Partner branch to enquire about NSFDC credit and education loan applications.',
    findPartners: 'Find Nearest Partners', gettingLocation: 'Getting your location…', findingBanks: 'Finding nearby banks…',
    showingNear: 'Showing banks near', yourLocation: 'your location',
    locationDenied: "Location access was blocked. Allow it in your browser's location settings and try again — this feature needs your real location to find real nearby branches.",
    lookupError: "Couldn't reach the bank-location lookup right now. Please try again in a moment.",
    noBranches: 'No bank branches found within range of your location. Try again from a location closer to a town or city center.',
    kmAway: 'km away', directions: 'Directions',
    npaDisclosure: "NPA / fund-utilization data for Channel Partners is not publicly available from any source — this deliberately uses real bank location data (OpenStreetMap) rather than fabricate an eligibility signal a citizen or partner could wrongly rely on.",
    moratoriumNote: 'month moratorium before EMIs begin',
    scheduleNote: 'repayment schedule below starts counting from month 1 after the moratorium ends.',
    incomeUpTo: 'annual family income up to',
}
const ALL_STATIC = Object.values(UI)

const TABS = [
    { id: 'recommend', label: 'tabRecommend', Icon: Landmark },
    { id: 'calculator', label: 'tabCalculator', Icon: Calculator },
    { id: 'locator', label: 'tabLocator', Icon: MapPin },
]

function RecommenderTab({ tr }) {
    const [projectType, setProjectType] = useState('business')
    const [estimatedCost, setEstimatedCost] = useState('')
    const [annualIncome, setAnnualIncome] = useState('')
    const [result, setResult] = useState(null)

    const handleRecommend = (e) => {
        e.preventDefault()
        const res = recommendScheme({
            projectType,
            estimatedCost: Number(estimatedCost) || 0,
            annualIncome: Number(annualIncome) || 0,
            isEducation: projectType === 'education',
        })
        setResult(res)
    }

    // Dynamic content generated at request time from the citizen's own
    // inputs (recommendScheme's reason/matchReason text) — this can't be
    // pre-registered by the parent's useAutoTranslate (which only sees
    // static strings known before any form submission), so it needs its
    // own registration call, scoped to whatever result is currently shown.
    const trDynamic = useAutoTranslate(
        result ? (result.eligible ? result.schemes.flatMap((s) => [s.matchReason]) : [result.reason]) : []
    )

    return (
        <div className="credit-tab-content">
            <form className="glass-card credit-form" onSubmit={handleRecommend}>
                <label className="credit-field">
                    <span>{tr(UI.forWhat)}</span>
                    <select className="input-glass" value={projectType} onChange={(e) => setProjectType(e.target.value)}>
                        <option value="business">{tr(UI.business)}</option>
                        <option value="education">{tr(UI.education)}</option>
                    </select>
                </label>

                {projectType !== 'education' && (
                    <label className="credit-field">
                        <span>{tr(UI.projectCost)}</span>
                        <input className="input-glass" type="number" min="0" value={estimatedCost}
                            onChange={(e) => setEstimatedCost(e.target.value)} placeholder={tr(UI.projectCostPh)} required />
                    </label>
                )}

                <label className="credit-field">
                    <span>{tr(UI.income)}</span>
                    <input className="input-glass" type="number" min="0" value={annualIncome}
                        onChange={(e) => setAnnualIncome(e.target.value)} placeholder={tr(UI.incomePh)} required />
                </label>

                <button type="submit" className="btn btn-primary">{tr(UI.recommendBtn)}</button>
            </form>

            {result && !result.eligible && (
                <div className="glass-card credit-result credit-result-ineligible">
                    <Info size={18} />
                    <p>{trDynamic(result.reason)}</p>
                </div>
            )}

            {result && result.eligible && result.schemes.map((s) => (
                <div key={s.id} className="glass-card credit-result">
                    <div className="credit-result-header">
                        {s.forProjectType === 'education' ? <GraduationCap size={20} /> : <IndianRupee size={20} />}
                        <h3>{tr(s.name)}</h3>
                    </div>
                    <p className="credit-result-desc">{tr(s.description)}</p>
                    <p className="credit-match-reason"><Info size={12} /> {trDynamic(s.matchReason)}</p>
                    <div className="credit-result-stats">
                        <div><span>{tr(UI.maxLoan)}</span><strong>{formatInr(s.maxLoanAmount)}</strong></div>
                        <div><span>{tr(UI.interestRate)}</span><strong>{s.interestRate}% p.a.</strong></div>
                        <div><span>{tr(UI.moratorium)}</span><strong>{s.moratoriumMonths} {tr(UI.months)}</strong></div>
                        <div><span>{tr(UI.coverage)}</span><strong>{tr(UI.upTo)} {s.coveragePct}%</strong></div>
                    </div>
                </div>
            ))}
        </div>
    )
}

function CalculatorTab({ tr }) {
    const [schemeId, setSchemeId] = useState(NSFDC_SCHEMES[0].id)
    const scheme = NSFDC_SCHEMES.find((s) => s.id === schemeId)
    const [amount, setAmount] = useState(scheme.maxLoanAmount / 2)
    const [tenureMonths, setTenureMonths] = useState(Math.round(scheme.maxTenureMonths / 2))

    const result = useMemo(() => calculateEmi(amount, scheme.interestRate, tenureMonths),
        [amount, scheme.interestRate, tenureMonths])

    const handleSchemeChange = (id) => {
        const s = NSFDC_SCHEMES.find((x) => x.id === id)
        setSchemeId(id)
        setAmount(Math.min(amount, s.maxLoanAmount))
        setTenureMonths(Math.min(tenureMonths, s.maxTenureMonths))
    }

    return (
        <div className="credit-tab-content">
            <div className="glass-card credit-form">
                <label className="credit-field">
                    <span>{tr(UI.scheme)}</span>
                    <select className="input-glass" value={schemeId} onChange={(e) => handleSchemeChange(e.target.value)}>
                        {NSFDC_SCHEMES.map((s) => <option key={s.id} value={s.id}>{tr(s.name)}</option>)}
                    </select>
                </label>

                <label className="credit-field">
                    <span>{tr(UI.loanAmount)} {formatInr(scheme.maxLoanAmount)})</span>
                    <input className="input-glass" type="number" min={scheme.minLoanAmount} max={scheme.maxLoanAmount}
                        value={amount} onChange={(e) => setAmount(Math.min(Number(e.target.value) || 0, scheme.maxLoanAmount))} />
                </label>

                <label className="credit-field">
                    <span>{tr(UI.repayTenure)} {scheme.maxTenureMonths})</span>
                    <input className="input-glass" type="number" min="1" max={scheme.maxTenureMonths}
                        value={tenureMonths} onChange={(e) => setTenureMonths(Math.min(Number(e.target.value) || 1, scheme.maxTenureMonths))} />
                </label>

                <p className="credit-scheme-note">
                    {scheme.interestRate}% p.a. · {scheme.moratoriumMonths}-{tr(UI.moratoriumNote)} ·
                    {tr(UI.scheduleNote)}
                </p>
            </div>

            <div className="glass-card credit-emi-summary">
                <div><span>{tr(UI.monthlyEmi)}</span><strong>{formatInr(result.emi)}</strong></div>
                <div><span>{tr(UI.totalInterest)}</span><strong>{formatInr(result.totalInterest)}</strong></div>
                <div><span>{tr(UI.totalPayment)}</span><strong>{formatInr(result.totalPayment)}</strong></div>
            </div>

            <details className="glass-card credit-schedule">
                <summary>{tr(UI.viewSchedule)}</summary>
                <div className="credit-schedule-table-wrap">
                    <table className="credit-schedule-table">
                        <thead>
                            <tr><th>{tr(UI.colMonth)}</th><th>{tr(UI.colEmi)}</th><th>{tr(UI.colPrincipal)}</th><th>{tr(UI.colInterest)}</th><th>{tr(UI.colBalance)}</th></tr>
                        </thead>
                        <tbody>
                            {result.schedule.map((row) => (
                                <tr key={row.month}>
                                    <td>{row.month}</td>
                                    <td>{formatInr(row.emi)}</td>
                                    <td>{formatInr(row.principalComponent)}</td>
                                    <td>{formatInr(row.interestComponent)}</td>
                                    <td>{formatInr(row.balance)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </details>
        </div>
    )
}

function LocatorTab({ tr }) {
    const [locStatus, setLocStatus] = useState('idle') // idle | enabling | denied
    const [loadStatus, setLoadStatus] = useState('idle') // idle | loading | done | error
    const [partners, setPartners] = useState([])
    const [note, setNote] = useState('')
    const [locationLabel, setLocationLabel] = useState('')
    // note/locationLabel come from the backend response — not known ahead of
    // time, so (like RecommenderTab's dynamic result text) they need their
    // own registration call rather than the parent's static-only list.
    const trDynamic = useAutoTranslate([note, locationLabel].filter(Boolean))

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

    return (
        <div className="credit-tab-content">
            <div className="glass-card credit-result">
                <div className="credit-result-header"><MapPin size={20} /><h3>{tr(UI.locatorTitle)}</h3></div>
                <p className="credit-result-desc">{tr(UI.locatorDesc)}</p>

                {loadStatus !== 'done' && (
                    <button className="btn btn-primary" onClick={enableLocation} disabled={locStatus === 'enabling' || loadStatus === 'loading'}>
                        {locStatus === 'enabling' ? tr(UI.gettingLocation) : loadStatus === 'loading' ? tr(UI.findingBanks) : tr(UI.findPartners)}
                    </button>
                )}

                {loadStatus === 'done' && (
                    <p className="credit-locator-denied" style={{ color: 'var(--text-subtle)' }}>
                        <MapPin size={13} /> {tr(UI.showingNear)} {(locationLabel && trDynamic(locationLabel)) || tr(UI.yourLocation)}
                    </p>
                )}

                {locStatus === 'denied' && (
                    <p className="credit-locator-denied">
                        <AlertTriangle size={13} /> {tr(UI.locationDenied)}
                    </p>
                )}
                {loadStatus === 'error' && (
                    <p className="credit-locator-denied">
                        <AlertTriangle size={13} /> {tr(UI.lookupError)}
                    </p>
                )}

                {note && (
                    <div className="credit-locator-mock-note">
                        <Info size={12} /> {trDynamic(note)}
                    </div>
                )}

                <div className="credit-locator-mock-note">
                    <AlertTriangle size={12} /> {tr(UI.npaDisclosure)}
                </div>
            </div>

            {loadStatus === 'done' && partners.length === 0 && (
                <div className="glass-card credit-result">
                    <p className="credit-result-desc">{tr(UI.noBranches)}</p>
                </div>
            )}

            {partners.map((p) => (
                <div key={`${p.name}-${p.lat}-${p.lng}`} className="glass-card credit-partner-card">
                    <div className="credit-partner-top">
                        <div>
                            <strong>{p.name}</strong>
                            <span className="credit-partner-type">{p.type}</span>
                        </div>
                    </div>
                    <div className="credit-partner-footer">
                        {p.distanceKm != null && <span>{p.distanceKm.toFixed(1)} {tr(UI.kmAway)}</span>}
                        <a href={`https://maps.google.com/?q=${p.lat},${p.lng}`} target="_blank" rel="noreferrer" className="credit-partner-action">
                            <Navigation size={12} /> {tr(UI.directions)}
                        </a>
                    </div>
                </div>
            ))}
        </div>
    )
}

export default function CreditSchemesPage() {
    const [tab, setTab] = useState('recommend')
    const tr = useAutoTranslate([
        ...ALL_STATIC,
        ...NSFDC_SCHEMES.flatMap((s) => [s.name, s.description]),
    ])

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content credit-schemes-page">
                <div className="credit-header">
                    <p className="credit-ps-tag">{tr(UI.psTag)}</p>
                    <h1>{tr(UI.title)}</h1>
                    <p>{tr(UI.subtitle)} — {tr(UI.incomeUpTo)} {formatInr(INCOME_CEILING)}.</p>
                </div>

                <div className="credit-tabs">
                    {TABS.map(({ id, label, Icon }) => (
                        <button key={id} className={`credit-tab-btn ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>
                            <Icon size={16} /> {tr(UI[label])}
                        </button>
                    ))}
                </div>

                {tab === 'recommend' && <RecommenderTab tr={tr} />}
                {tab === 'calculator' && <CalculatorTab tr={tr} />}
                {tab === 'locator' && <LocatorTab tr={tr} />}
            </main>
            <BottomNav />
        </div>
    )
}
