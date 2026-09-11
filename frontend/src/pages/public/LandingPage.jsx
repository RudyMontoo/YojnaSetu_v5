import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowRight, ClipboardCheck, Landmark, Calculator, MapPin, ShieldCheck } from 'lucide-react'
import { PublicPage } from '../../components/PublicShell'
import { gateway } from '../../lib/api'
import { formatInr } from '../../lib/emiCalculator'
import { useAutoTranslate } from '../../lib/i18n'
import './PublicPages.css'

const UI = {
    eyebrow: 'Ministry of Social Justice & Empowerment · NSFDC',
    title: 'Concessional Credit Schemes for SC Beneficiaries',
    sub: 'Check eligibility, compare schemes, calculate EMI, and find nearby branches — all in one place. No account needed to look around.',
    ctaPrimary: 'Check Your Eligibility',
    ctaSecondary: 'Browse All Schemes',
    schemesTitle: 'Available schemes',
    schemesSub: 'Concessional loans for self-employment, business, and education.',
    viewAll: 'View all schemes',
    maxLoan: 'Maximum loan',
    rate: 'Interest rate',
    toolsTitle: 'Tools you can use right now',
    toolEligibility: 'Eligibility checker',
    toolEligibilityDesc: 'Answer four short questions and see which schemes you indicatively qualify for.',
    toolEmi: 'EMI calculator',
    toolEmiDesc: 'Work out your monthly repayment, including the months before EMIs begin.',
    toolLocator: 'Find a branch',
    toolLocatorDesc: 'Locate Channel Partner bank branches near you to enquire in person.',
    noLogin: 'No login needed',
    loadError: "Couldn't load the scheme list right now. Please refresh in a moment.",
    perYear: 'per year',
}

export default function LandingPage() {
    const navigate = useNavigate()
    const [products, setProducts] = useState([])
    const [failed, setFailed] = useState(false)

    useEffect(() => {
        gateway.creditProducts()
            .then((list) => setProducts(Array.isArray(list) ? list : []))
            .catch(() => setFailed(true))
    }, [])

    const featured = products.slice(0, 3)
    const tr = useAutoTranslate([
        ...Object.values(UI),
        ...featured.map((p) => p.name),
        ...featured.map((p) => p.description),
    ])

    return (
        <PublicPage tr={tr}>
            <section className="gov-hero">
                <div className="gov-container">
                    <span className="gov-eyebrow">{tr(UI.eyebrow)}</span>
                    <h1>{tr(UI.title)}</h1>
                    <p className="gov-hero-sub">{tr(UI.sub)}</p>
                    <div className="gov-hero-actions">
                        <button className="gov-btn gov-btn-primary" onClick={() => navigate('/eligibility')}>
                            <ClipboardCheck size={18} /> {tr(UI.ctaPrimary)}
                        </button>
                        <button className="gov-btn gov-btn-secondary" onClick={() => navigate('/credit-schemes')}>
                            {tr(UI.ctaSecondary)} <ArrowRight size={17} />
                        </button>
                    </div>
                </div>
            </section>

            <section className="gov-section">
                <div className="gov-container">
                    <h2 className="gov-section-title">{tr(UI.schemesTitle)}</h2>
                    <p className="gov-section-sub">{tr(UI.schemesSub)}</p>

                    {failed ? (
                        <div className="gov-notice gov-notice-error">{tr(UI.loadError)}</div>
                    ) : (
                        <>
                            <div className="gov-grid">
                                {featured.map((p) => (
                                    <Link
                                        key={p.id}
                                        to={`/credit-schemes/${p.id}`}
                                        className="gov-card gov-scheme-card"
                                        style={{ textDecoration: 'none' }}
                                    >
                                        <div>
                                            <span className="gov-scheme-code">{p.code}</span>
                                            <h3>{tr(p.name)}</h3>
                                        </div>
                                        <p className="gov-scheme-desc">{tr(p.description)}</p>
                                        <div className="gov-facts">
                                            <div>
                                                <div className="gov-fact-label">{tr(UI.maxLoan)}</div>
                                                {/* From the backend catalogue — the loan cap, never the
                                                    project-cost ceiling, which is a different number. */}
                                                <div className="gov-fact-value">{formatInr(p.maxLoanAmount)}</div>
                                            </div>
                                            <div>
                                                <div className="gov-fact-label">{tr(UI.rate)}</div>
                                                <div className="gov-fact-value">{p.interestRate}%</div>
                                            </div>
                                        </div>
                                    </Link>
                                ))}
                            </div>
                            {products.length > featured.length && (
                                <div style={{ marginTop: 16 }}>
                                    <Link to="/credit-schemes" className="gov-btn gov-btn-ghost gov-btn-sm">
                                        {tr(UI.viewAll)} ({products.length}) <ArrowRight size={15} />
                                    </Link>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </section>

            <section className="gov-section" style={{ paddingTop: 0 }}>
                <div className="gov-container">
                    <h2 className="gov-section-title">{tr(UI.toolsTitle)}</h2>
                    <p className="gov-section-sub">
                        <span className="gov-badge gov-badge-ok"><ShieldCheck size={12} /> {tr(UI.noLogin)}</span>
                    </p>
                    <div className="gov-grid">
                        <Link to="/eligibility" className="gov-card gov-scheme-card" style={{ textDecoration: 'none' }}>
                            <h3><ClipboardCheck size={17} style={{ verticalAlign: '-3px' }} /> {tr(UI.toolEligibility)}</h3>
                            <p className="gov-scheme-desc">{tr(UI.toolEligibilityDesc)}</p>
                        </Link>
                        <Link to="/emi-calculator" className="gov-card gov-scheme-card" style={{ textDecoration: 'none' }}>
                            <h3><Calculator size={17} style={{ verticalAlign: '-3px' }} /> {tr(UI.toolEmi)}</h3>
                            <p className="gov-scheme-desc">{tr(UI.toolEmiDesc)}</p>
                        </Link>
                        <Link to="/partner-locator" className="gov-card gov-scheme-card" style={{ textDecoration: 'none' }}>
                            <h3><MapPin size={17} style={{ verticalAlign: '-3px' }} /> {tr(UI.toolLocator)}</h3>
                            <p className="gov-scheme-desc">{tr(UI.toolLocatorDesc)}</p>
                        </Link>
                    </div>
                </div>
            </section>
        </PublicPage>
    )
}
