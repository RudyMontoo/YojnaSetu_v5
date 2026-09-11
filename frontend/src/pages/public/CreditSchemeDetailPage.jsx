import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Users, Info, FileText, Calculator, CheckCircle2, ExternalLink } from 'lucide-react'
import { PublicPage } from '../../components/PublicShell'
import LoginPrompt from '../../components/LoginPrompt'
import { isGuest } from '../../lib/auth'
import { gateway } from '../../lib/api'
import { calculateEmi, formatInr } from '../../lib/emiCalculator'
import { useAutoTranslate } from '../../lib/i18n'
import './PublicPages.css'

const UI = {
    back: 'All schemes',
    notFound: 'That scheme could not be found.',
    loading: 'Loading…',
    loadError: "Couldn't load this scheme right now. Please refresh in a moment.",
    womenOnly: 'Women applicants only',
    unverified: 'Figures not independently verified',
    whoTitle: 'Who can apply',
    whoCategory: 'Social category',
    whoIncome: 'Annual family income must not exceed',
    whoProject: 'Project cost this scheme covers',
    whoWomen: 'This scheme is for women applicants only, and carries a lower interest rate than the general schemes.',
    benefitsTitle: 'What you get',
    maxLoan: 'Maximum loan',
    maxLoanNote: 'This is the most you can borrow. It is not the same as the project cost the scheme covers — you contribute the difference yourself.',
    rate: 'Interest rate',
    perYear: 'per year',
    noEmi: 'No EMI for the first',
    months: 'months',
    repay: 'Repay over up to',
    coverage: 'Loan covers up to',
    ofProjectCost: 'of the project cost',
    marginNote: 'The rest is your own contribution, called margin money. Plan for it early — it is the most common reason an application stalls.',
    docsTitle: 'Documents usually needed',
    docsNote: 'The branch confirms the exact list for your case. Keep clear photos or scans ready (PDF, JPG or PNG).',
    emiTitle: 'Example repayment',
    emiNote: 'An illustration using the maximum loan at this scheme\'s rate and tenure. Use the calculator for your own numbers.',
    emiMonthly: 'Monthly EMI',
    emiTotalInterest: 'Total interest',
    emiTotalPaid: 'Total you repay',
    openCalc: 'Open EMI calculator',
    applyNow: 'Apply for this scheme',
    checkFirst: 'Check my eligibility first',
    sourceTitle: 'Where these figures come from',
    officialPage: 'Official scheme page',
    loginToApply: 'apply for this scheme',
    loginBody: 'You can keep reading this page without an account. An account is only needed to actually submit an application, so we can track it for you.',
    deliveredBy: 'Available through',
}

// The backend deliberately models no per-scheme document list (documentType on
// an upload is free text), so this is presented as guidance, not as data
// pulled from the catalogue — and the copy says the branch confirms the real
// list. Inventing a per-scheme list in the API would look authoritative
// without anything standing behind it.
const COMMON_DOCS = [
    'Aadhaar card',
    'Caste certificate (SC)',
    'Income certificate (current year)',
    'Bank passbook or cancelled cheque',
    'Passport-size photograph',
]
const BUSINESS_DOCS = ['Project proposal or cost estimate / quotation']
const EDUCATION_DOCS = ['Admission letter from the institution', 'Fee structure for the course']

export default function CreditSchemeDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [product, setProduct] = useState(null)
    const [state, setState] = useState('loading') // loading | ready | missing | error
    const [promptOpen, setPromptOpen] = useState(false)

    useEffect(() => {
        let cancelled = false
        gateway.creditProducts()
            .then((list) => {
                if (cancelled) return
                const found = (Array.isArray(list) ? list : []).find((p) => p.id === id || p.code === id)
                setProduct(found || null)
                setState(found ? 'ready' : 'missing')
            })
            .catch(() => { if (!cancelled) setState('error') })
        return () => { cancelled = true }
    }, [id])

    const docs = useMemo(() => {
        if (!product) return COMMON_DOCS
        return product.type === 'education'
            ? [...COMMON_DOCS, ...EDUCATION_DOCS]
            : [...COMMON_DOCS, ...BUSINESS_DOCS]
    }, [product])

    // Illustration only — computed locally with the same tested helper the
    // calculator uses, at the scheme's own maximum so the number is concrete.
    const example = useMemo(() => {
        if (!product) return null
        return calculateEmi(product.maxLoanAmount, product.interestRate, product.maxTenureMonths, {
            moratoriumMonths: product.moratoriumMonths,
        })
    }, [product])

    const tr = useAutoTranslate([
        ...Object.values(UI), ...docs,
        product?.name, product?.description, product?.sourceNote,
    ].filter(Boolean))

    const onApply = () => {
        if (isGuest()) { setPromptOpen(true); return }
        navigate(`/apply/${product.id}`, { state: { productId: product.id, schemeCode: product.code } })
    }

    return (
        <PublicPage tr={tr}>
            <div className="gov-container gov-narrow" style={{ paddingTop: 22, paddingBottom: 8 }}>
                <button className="gov-back" onClick={() => navigate('/credit-schemes')}>
                    <ArrowLeft size={16} /> {tr(UI.back)}
                </button>

                {state === 'loading' && <div className="gov-empty">{tr(UI.loading)}</div>}
                {state === 'error' && <div className="gov-notice gov-notice-error">{tr(UI.loadError)}</div>}
                {state === 'missing' && <div className="gov-notice gov-notice-warn">{tr(UI.notFound)}</div>}

                {state === 'ready' && product && (
                    <>
                        <span className="gov-scheme-code">{product.code}</span>
                        <h1 style={{ fontSize: 26, marginTop: 4 }}>{tr(product.name)}</h1>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '10px 0 14px' }}>
                            {product.womenOnly && (
                                <span className="gov-badge gov-badge-muted"><Users size={11} /> {tr(UI.womenOnly)}</span>
                            )}
                            {product.figuresVerified === false && (
                                <span className="gov-badge gov-badge-warn"><Info size={11} /> {tr(UI.unverified)}</span>
                            )}
                        </div>
                        <p style={{ fontSize: 15, lineHeight: 1.6, marginBottom: 22 }}>{tr(product.description)}</p>

                        {/* ── what you get ── */}
                        <div className="gov-card" style={{ marginBottom: 16 }}>
                            <h2 className="gov-section-title" style={{ fontSize: 17, marginBottom: 14 }}>{tr(UI.benefitsTitle)}</h2>
                            <div className="gov-facts">
                                <div>
                                    <div className="gov-fact-label">{tr(UI.maxLoan)}</div>
                                    <div className="gov-fact-value">{formatInr(product.maxLoanAmount)}</div>
                                </div>
                                <div>
                                    <div className="gov-fact-label">{tr(UI.rate)}</div>
                                    <div className="gov-fact-value">{product.interestRate}% <span style={{ fontWeight: 400, fontSize: 12 }}>{tr(UI.perYear)}</span></div>
                                </div>
                                <div>
                                    <div className="gov-fact-label">{tr(UI.noEmi)}</div>
                                    <div className="gov-fact-value">{product.moratoriumMonths} {tr(UI.months)}</div>
                                </div>
                                <div>
                                    <div className="gov-fact-label">{tr(UI.repay)}</div>
                                    <div className="gov-fact-value">{product.maxTenureMonths} {tr(UI.months)}</div>
                                </div>
                            </div>
                            <p className="gov-hint">{tr(UI.maxLoanNote)}</p>
                            <div className="gov-notice gov-notice-info" style={{ marginTop: 14 }}>
                                <Info size={16} />
                                <span>
                                    <strong>{tr(UI.coverage)} {product.coveragePct}% {tr(UI.ofProjectCost)}.</strong>{' '}
                                    {tr(UI.marginNote)}
                                </span>
                            </div>
                        </div>

                        {/* ── who can apply ── */}
                        <div className="gov-card" style={{ marginBottom: 16 }}>
                            <h2 className="gov-section-title" style={{ fontSize: 17, marginBottom: 12 }}>{tr(UI.whoTitle)}</h2>
                            <div className="gov-facts">
                                <div>
                                    <div className="gov-fact-label">{tr(UI.whoCategory)}</div>
                                    <div className="gov-fact-value" style={{ textTransform: 'uppercase' }}>
                                        {(product.categories || []).join(', ') || 'SC'}
                                    </div>
                                </div>
                                <div>
                                    <div className="gov-fact-label">{tr(UI.whoIncome)}</div>
                                    <div className="gov-fact-value">{formatInr(product.maxAnnualIncome)}</div>
                                </div>
                            </div>
                            {(product.unitCostFloor || product.unitCostCeiling) && (
                                <p className="gov-hint">
                                    {tr(UI.whoProject)}:{' '}
                                    {product.unitCostFloor ? formatInr(product.unitCostFloor) : formatInr(0)}
                                    {' – '}
                                    {product.unitCostCeiling ? formatInr(product.unitCostCeiling) : '—'}
                                </p>
                            )}
                            {product.womenOnly && <p className="gov-hint">{tr(UI.whoWomen)}</p>}
                            {product.channelPartnerTypes?.length > 0 && (
                                <p className="gov-hint">
                                    {tr(UI.deliveredBy)}: {product.channelPartnerTypes.join(', ')}
                                </p>
                            )}
                        </div>

                        {/* ── documents ── */}
                        <div className="gov-card" style={{ marginBottom: 16 }}>
                            <h2 className="gov-section-title" style={{ fontSize: 17, marginBottom: 10 }}>
                                <FileText size={17} style={{ verticalAlign: '-3px' }} /> {tr(UI.docsTitle)}
                            </h2>
                            <ul className="gov-reason" style={{ paddingLeft: 18, margin: 0 }}>
                                {docs.map((d) => <li key={d}>{tr(d)}</li>)}
                            </ul>
                            <p className="gov-hint">{tr(UI.docsNote)}</p>
                        </div>

                        {/* ── example EMI ── */}
                        {example && (
                            <div className="gov-card" style={{ marginBottom: 16 }}>
                                <h2 className="gov-section-title" style={{ fontSize: 17, marginBottom: 12 }}>
                                    <Calculator size={17} style={{ verticalAlign: '-3px' }} /> {tr(UI.emiTitle)}
                                </h2>
                                <div className="gov-facts">
                                    <div>
                                        <div className="gov-fact-label">{tr(UI.emiMonthly)}</div>
                                        <div className="gov-fact-value">{formatInr(example.emi)}</div>
                                    </div>
                                    <div>
                                        <div className="gov-fact-label">{tr(UI.emiTotalInterest)}</div>
                                        <div className="gov-fact-value">{formatInr(example.totalInterest)}</div>
                                    </div>
                                </div>
                                <p className="gov-hint">{tr(UI.emiNote)}</p>
                                <Link to="/emi-calculator" className="gov-btn gov-btn-ghost gov-btn-sm" style={{ marginTop: 10 }}>
                                    {tr(UI.openCalc)}
                                </Link>
                            </div>
                        )}

                        {/* ── provenance ── */}
                        {product.sourceNote && (
                            <div className="gov-card" style={{ marginBottom: 16 }}>
                                <h2 className="gov-section-title" style={{ fontSize: 15, marginBottom: 8 }}>{tr(UI.sourceTitle)}</h2>
                                <p className="gov-hint" style={{ marginTop: 0 }}>{tr(product.sourceNote)}</p>
                                {product.sourceUrl && (
                                    <a href={product.sourceUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13 }}>
                                        {tr(UI.officialPage)} <ExternalLink size={12} style={{ verticalAlign: '-1px' }} />
                                    </a>
                                )}
                            </div>
                        )}

                        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 30 }}>
                            <button className="gov-btn gov-btn-primary" onClick={onApply} style={{ flex: '1 1 200px' }}>
                                <CheckCircle2 size={17} /> {tr(UI.applyNow)}
                            </button>
                            <Link to="/eligibility" className="gov-btn gov-btn-secondary" style={{ flex: '1 1 180px' }}>
                                {tr(UI.checkFirst)}
                            </Link>
                        </div>
                    </>
                )}
            </div>

            <LoginPrompt open={promptOpen} onClose={() => setPromptOpen(false)} action={tr(UI.loginToApply)}>
                {tr(UI.loginBody)}
            </LoginPrompt>
        </PublicPage>
    )
}
