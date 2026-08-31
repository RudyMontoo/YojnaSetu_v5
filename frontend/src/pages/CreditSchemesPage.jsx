import { useState, useMemo } from 'react'
import { Landmark, Calculator, MapPin, IndianRupee, GraduationCap, Info, Navigation, AlertTriangle } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { recommendScheme, NSFDC_SCHEMES, INCOME_CEILING } from '../lib/nsfdcSchemes'
import { calculateEmi, formatInr } from '../lib/emiCalculator'
import { gateway } from '../lib/api'
import '../components/components.css'
import './CreditSchemesPage.css'

const TABS = [
    { id: 'recommend', label: 'Scheme Recommender', Icon: Landmark },
    { id: 'calculator', label: 'EMI Calculator', Icon: Calculator },
    { id: 'locator', label: 'Partner Locator', Icon: MapPin },
]

function RecommenderTab() {
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

    return (
        <div className="credit-tab-content">
            <form className="glass-card credit-form" onSubmit={handleRecommend}>
                <label className="credit-field">
                    <span>What is this for?</span>
                    <select className="input-glass" value={projectType} onChange={(e) => setProjectType(e.target.value)}>
                        <option value="business">Business / self-employment project</option>
                        <option value="education">Education (course, tuition, hostel)</option>
                    </select>
                </label>

                {projectType !== 'education' && (
                    <label className="credit-field">
                        <span>Estimated project cost (₹)</span>
                        <input className="input-glass" type="number" min="0" value={estimatedCost}
                            onChange={(e) => setEstimatedCost(e.target.value)} placeholder="e.g. 80000" required />
                    </label>
                )}

                <label className="credit-field">
                    <span>Annual family income (₹)</span>
                    <input className="input-glass" type="number" min="0" value={annualIncome}
                        onChange={(e) => setAnnualIncome(e.target.value)} placeholder="e.g. 300000" required />
                </label>

                <button type="submit" className="btn btn-primary">Recommend a Scheme</button>
            </form>

            {result && !result.eligible && (
                <div className="glass-card credit-result credit-result-ineligible">
                    <Info size={18} />
                    <p>{result.reason}</p>
                </div>
            )}

            {result && result.eligible && result.schemes.map((s) => (
                <div key={s.id} className="glass-card credit-result">
                    <div className="credit-result-header">
                        {s.forProjectType === 'education' ? <GraduationCap size={20} /> : <IndianRupee size={20} />}
                        <h3>{s.name}</h3>
                    </div>
                    <p className="credit-result-desc">{s.description}</p>
                    <p className="credit-match-reason"><Info size={12} /> {s.matchReason}</p>
                    <div className="credit-result-stats">
                        <div><span>Max loan</span><strong>{formatInr(s.maxLoanAmount)}</strong></div>
                        <div><span>Interest rate</span><strong>{s.interestRate}% p.a.</strong></div>
                        <div><span>Moratorium</span><strong>{s.moratoriumMonths} months</strong></div>
                        <div><span>Coverage</span><strong>up to {s.coveragePct}%</strong></div>
                    </div>
                </div>
            ))}
        </div>
    )
}

function CalculatorTab() {
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
                    <span>Scheme</span>
                    <select className="input-glass" value={schemeId} onChange={(e) => handleSchemeChange(e.target.value)}>
                        {NSFDC_SCHEMES.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                </label>

                <label className="credit-field">
                    <span>Loan amount (max {formatInr(scheme.maxLoanAmount)})</span>
                    <input className="input-glass" type="number" min={scheme.minLoanAmount} max={scheme.maxLoanAmount}
                        value={amount} onChange={(e) => setAmount(Math.min(Number(e.target.value) || 0, scheme.maxLoanAmount))} />
                </label>

                <label className="credit-field">
                    <span>Repayment tenure in months (max {scheme.maxTenureMonths})</span>
                    <input className="input-glass" type="number" min="1" max={scheme.maxTenureMonths}
                        value={tenureMonths} onChange={(e) => setTenureMonths(Math.min(Number(e.target.value) || 1, scheme.maxTenureMonths))} />
                </label>

                <p className="credit-scheme-note">
                    {scheme.interestRate}% p.a. · {scheme.moratoriumMonths}-month moratorium before EMIs begin ·
                    repayment schedule below starts counting from month 1 after the moratorium ends.
                </p>
            </div>

            <div className="glass-card credit-emi-summary">
                <div><span>Monthly EMI</span><strong>{formatInr(result.emi)}</strong></div>
                <div><span>Total interest</span><strong>{formatInr(result.totalInterest)}</strong></div>
                <div><span>Total payment</span><strong>{formatInr(result.totalPayment)}</strong></div>
            </div>

            <details className="glass-card credit-schedule">
                <summary>View month-by-month repayment schedule</summary>
                <div className="credit-schedule-table-wrap">
                    <table className="credit-schedule-table">
                        <thead>
                            <tr><th>Month</th><th>EMI</th><th>Principal</th><th>Interest</th><th>Balance</th></tr>
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

function LocatorTab() {
    const [locStatus, setLocStatus] = useState('idle') // idle | enabling | denied
    const [loadStatus, setLoadStatus] = useState('idle') // idle | loading | done | error
    const [partners, setPartners] = useState([])
    const [note, setNote] = useState('')
    const [locationLabel, setLocationLabel] = useState('')

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
                <div className="credit-result-header"><MapPin size={20} /><h3>Partner Locator</h3></div>
                <p className="credit-result-desc">
                    Finds real bank branches near your current location using OpenStreetMap data, to help you find a Channel Partner branch to enquire about NSFDC credit and education loan applications.
                </p>

                {loadStatus !== 'done' && (
                    <button className="btn btn-primary" onClick={enableLocation} disabled={locStatus === 'enabling' || loadStatus === 'loading'}>
                        {locStatus === 'enabling' ? 'Getting your location…' : loadStatus === 'loading' ? 'Finding nearby banks…' : 'Find Nearest Partners'}
                    </button>
                )}

                {loadStatus === 'done' && (
                    <p className="credit-locator-denied" style={{ color: 'var(--text-subtle)' }}>
                        <MapPin size={13} /> Showing banks near {locationLabel || 'your location'}
                    </p>
                )}

                {locStatus === 'denied' && (
                    <p className="credit-locator-denied">
                        <AlertTriangle size={13} /> Location access was blocked. Allow it in your browser's location settings and try again — this feature needs your real location to find real nearby branches.
                    </p>
                )}
                {loadStatus === 'error' && (
                    <p className="credit-locator-denied">
                        <AlertTriangle size={13} /> Couldn't reach the bank-location lookup right now. Please try again in a moment.
                    </p>
                )}

                {note && (
                    <div className="credit-locator-mock-note">
                        <Info size={12} /> {note}
                    </div>
                )}
            </div>

            {loadStatus === 'done' && partners.length === 0 && (
                <div className="glass-card credit-result">
                    <p className="credit-result-desc">No bank branches found within range of your location. Try again from a location closer to a town or city center.</p>
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
                        {p.distanceKm != null && <span>{p.distanceKm.toFixed(1)} km away</span>}
                        <a href={`https://maps.google.com/?q=${p.lat},${p.lng}`} target="_blank" rel="noreferrer" className="credit-partner-action">
                            <Navigation size={12} /> Directions
                        </a>
                    </div>
                </div>
            ))}
        </div>
    )
}

export default function CreditSchemesPage() {
    const [tab, setTab] = useState('recommend')

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content credit-schemes-page">
                <div className="credit-header">
                    <h1>NSFDC Credit &amp; Education Loans</h1>
                    <p>Concessional financing for the SC community — annual family income up to {formatInr(INCOME_CEILING)}.</p>
                </div>

                <div className="credit-tabs">
                    {TABS.map(({ id, label, Icon }) => (
                        <button key={id} className={`credit-tab-btn ${tab === id ? 'active' : ''}`} onClick={() => setTab(id)}>
                            <Icon size={16} /> {label}
                        </button>
                    ))}
                </div>

                {tab === 'recommend' && <RecommenderTab />}
                {tab === 'calculator' && <CalculatorTab />}
                {tab === 'locator' && <LocatorTab />}
            </main>
            <BottomNav />
        </div>
    )
}
