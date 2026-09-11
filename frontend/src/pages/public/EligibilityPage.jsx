import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ClipboardCheck, CheckCircle2, XCircle, HelpCircle, Lock, ArrowRight } from 'lucide-react'
import { PublicPage } from '../../components/PublicShell'
import LoginPrompt from '../../components/LoginPrompt'
import { isGuest } from '../../lib/auth'
import { gateway } from '../../lib/api'
import { formatInr } from '../../lib/emiCalculator'
import { useAutoTranslate } from '../../lib/i18n'
import './PublicPages.css'

const UI = {
    title: 'Check your eligibility',
    sub: 'Four short questions. No account needed, and nothing is saved unless you ask us to.',
    privacy: 'Your answers are used only to work out which schemes you qualify for. They are not stored or shared unless you create an account and apply.',
    needLabel: 'What do you need the loan for?',
    needBusiness: 'Business or self-employment',
    needEducation: 'Education (course, tuition, hostel)',
    costLabel: 'Roughly how much will it cost, in total?',
    costHint: 'The full project or course cost — not the amount you want to borrow.',
    incomeLabel: 'Your annual family income',
    incomeHint: 'All earners in the household, over a year.',
    genderLabel: 'Applicant',
    genderFemale: 'Woman',
    genderMale: 'Man',
    genderOther: 'Other',
    genderHint: 'Asked because some schemes are for women only and carry a lower interest rate — without this we cannot tell you if you qualify for a cheaper option.',
    categoryLabel: 'Social category',
    submit: 'Show my schemes',
    checking: 'Checking…',
    resultsTitle: 'Your indicative results',
    indicative: 'Indicative only — the lending branch makes the final decision.',
    eligible: 'You appear to qualify',
    notEligible: 'You do not appear to qualify',
    unknown: 'We need a little more information',
    needMore: 'To give you a clear answer, we still need:',
    youCanBorrow: 'You could borrow up to',
    marginMoney: 'Your own contribution (margin money)',
    monthlyEmi: 'Indicative monthly EMI',
    why: 'Why',
    whyNot: 'Why not',
    rate: 'Interest rate',
    costCapped: 'Your project costs more than this scheme funds, so the figures above are capped at the scheme maximum.',
    viewScheme: 'View scheme',
    applyNow: 'Apply for this scheme',
    saveResults: 'Save these results',
    loginToApply: 'apply for this scheme',
    loginToSave: 'save your results',
    loginSaveBody: 'Create an account to keep these results, come back to them later, and apply when you are ready.',
    error: "Couldn't check eligibility right now. Please try again in a moment.",
    noMatch: 'No scheme matched your answers. You can still browse all schemes, or ask for help at a nearby centre.',
    browseAll: 'Browse all schemes',
    fixCost: 'Please enter a project cost greater than zero.',
}

// The API returns raw field names here; a citizen should see a question, not
// a variable name.
const MISSING_LABELS = {
    estimatedCost: 'how much your project or course will cost',
    annualIncome: 'your annual family income',
    category: 'your social category',
    gender: 'whether the applicant is a woman (some schemes are women-only)',
}

export default function EligibilityPage() {
    const navigate = useNavigate()
    const [need, setNeed] = useState('business')
    const [estimatedCost, setCost] = useState('')
    const [annualIncome, setIncome] = useState('')
    const [gender, setGender] = useState('')
    const [category, setCategory] = useState('sc')
    const [result, setResult] = useState(null)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')
    const [prompt, setPrompt] = useState(null) // null | {action, body}

    const tr = useAutoTranslate([
        ...Object.values(UI),
        ...Object.values(MISSING_LABELS),
        ...(result?.recommendations || []).flatMap((r) => [r.name, ...(r.matched || []), ...(r.failed || [])]),
        result?.note,
    ].filter(Boolean))

    const submit = async (e) => {
        e.preventDefault()
        const cost = Number(estimatedCost)
        if (!cost || cost <= 0) { setError(tr(UI.fixCost)); return }
        setBusy(true); setError(''); setResult(null)
        try {
            const res = await gateway.checkEligibility({
                need,
                estimatedCost: cost,
                annualIncome: annualIncome === '' ? null : Number(annualIncome),
                category: category || null,
                gender: gender || null,
            })
            setResult(res)
        } catch (err) {
            setError(err.message || tr(UI.error))
        } finally {
            setBusy(false)
        }
    }

    const onApply = (rec) => {
        if (isGuest()) { setPrompt({ action: tr(UI.loginToApply), body: tr(UI.loginSaveBody) }); return }
        navigate(`/apply/${rec.productId}`, { state: { productId: rec.productId, schemeCode: rec.code, estimatedCost: Number(estimatedCost), annualIncome: Number(annualIncome) || null, category, gender, need } })
    }

    const onSave = () => {
        if (isGuest()) { setPrompt({ action: tr(UI.loginToSave), body: tr(UI.loginSaveBody) }); return }
        navigate('/home')
    }

    const verdictUi = {
        eligible: { icon: <CheckCircle2 size={16} />, cls: 'gov-notice-ok', text: UI.eligible },
        not_eligible: { icon: <XCircle size={16} />, cls: 'gov-notice-error', text: UI.notEligible },
        insufficient_data: { icon: <HelpCircle size={16} />, cls: 'gov-notice-warn', text: UI.unknown },
    }[result?.verdict]

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
                    <form onSubmit={submit} className="gov-card" style={{ marginBottom: 22 }}>
                        <div className="gov-field">
                            <span className="gov-label">{tr(UI.needLabel)}</span>
                            <div className="gov-radio-row">
                                {[['business', UI.needBusiness], ['education', UI.needEducation]].map(([val, label]) => (
                                    <label key={val} className={`gov-radio ${need === val ? 'active' : ''}`}>
                                        <input type="radio" name="need" value={val} checked={need === val} onChange={() => setNeed(val)} />
                                        {tr(label)}
                                    </label>
                                ))}
                            </div>
                        </div>

                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.costLabel)}</span>
                            <input className="gov-input" inputMode="numeric" value={estimatedCost}
                                onChange={(e) => setCost(e.target.value.replace(/[^0-9]/g, ''))}
                                placeholder="80000" required />
                            <span className="gov-hint">{tr(UI.costHint)}</span>
                        </label>

                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.incomeLabel)}</span>
                            <input className="gov-input" inputMode="numeric" value={annualIncome}
                                onChange={(e) => setIncome(e.target.value.replace(/[^0-9]/g, ''))}
                                placeholder="300000" />
                            <span className="gov-hint">{tr(UI.incomeHint)}</span>
                        </label>

                        <div className="gov-field">
                            <span className="gov-label">{tr(UI.genderLabel)}</span>
                            <div className="gov-radio-row">
                                {[['female', UI.genderFemale], ['male', UI.genderMale], ['other', UI.genderOther]].map(([val, label]) => (
                                    <label key={val} className={`gov-radio ${gender === val ? 'active' : ''}`}>
                                        <input type="radio" name="gender" value={val} checked={gender === val} onChange={() => setGender(val)} />
                                        {tr(label)}
                                    </label>
                                ))}
                            </div>
                            <span className="gov-hint">{tr(UI.genderHint)}</span>
                        </div>

                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.categoryLabel)}</span>
                            <select className="gov-select" value={category} onChange={(e) => setCategory(e.target.value)}>
                                <option value="sc">SC</option>
                                <option value="st">ST</option>
                                <option value="obc">OBC</option>
                                <option value="general">General</option>
                            </select>
                        </label>

                        {error && <div className="gov-notice gov-notice-error" style={{ marginBottom: 14 }}>{error}</div>}

                        <button type="submit" className="gov-btn gov-btn-primary" disabled={busy} style={{ width: '100%' }}>
                            {busy ? <><span className="gov-spinner" /> {tr(UI.checking)}</> : <><ClipboardCheck size={17} /> {tr(UI.submit)}</>}
                        </button>

                        <p className="gov-hint" style={{ marginTop: 14 }}>
                            <Lock size={12} style={{ verticalAlign: '-2px' }} /> {tr(UI.privacy)}
                        </p>
                    </form>

                    {result && (
                        <>
                            <h2 className="gov-section-title">{tr(UI.resultsTitle)}</h2>
                            <p className="gov-section-sub">{tr(UI.indicative)}</p>

                            {verdictUi && (
                                <div className={`gov-notice ${verdictUi.cls}`} style={{ marginBottom: 16 }}>
                                    {verdictUi.icon}
                                    <span>
                                        <strong>{tr(verdictUi.text)}</strong>
                                        {result.note && <><br />{tr(result.note)}</>}
                                    </span>
                                </div>
                            )}

                            {result.missingProfileData?.length > 0 && (
                                <div className="gov-card" style={{ marginBottom: 16 }}>
                                    <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{tr(UI.needMore)}</p>
                                    <ul className="gov-reason" style={{ paddingLeft: 18, margin: 0 }}>
                                        {[...new Set(result.missingProfileData)].map((f) => (
                                            <li key={f}>{tr(MISSING_LABELS[f] || f)}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {(result.recommendations || []).length === 0 && (
                                <div className="gov-empty">
                                    <p style={{ marginBottom: 14 }}>{tr(UI.noMatch)}</p>
                                    <Link to="/credit-schemes" className="gov-btn gov-btn-secondary gov-btn-sm">{tr(UI.browseAll)}</Link>
                                </div>
                            )}

                            {(result.recommendations || []).map((rec) => (
                                <div
                                    key={rec.productId}
                                    className={`gov-card gov-result ${rec.eligible ? 'eligible' : (rec.missingProfileData?.length ? 'unknown' : 'not-eligible')}`}
                                    style={{ marginBottom: 14 }}
                                >
                                    <span className="gov-scheme-code">{rec.code}</span>
                                    <h3 style={{ fontSize: 17, marginBottom: 10 }}>{tr(rec.name)}</h3>

                                    {rec.eligible && (
                                        <div className="gov-facts" style={{ marginBottom: 10 }}>
                                            <div>
                                                <div className="gov-fact-label">{tr(UI.youCanBorrow)}</div>
                                                <div className="gov-fact-value">{formatInr(rec.eligibleLoanAmount ?? rec.maxLoanAmount)}</div>
                                            </div>
                                            <div>
                                                <div className="gov-fact-label">{tr(UI.marginMoney)}</div>
                                                <div className="gov-fact-value">{formatInr(rec.marginMoney ?? 0)}</div>
                                            </div>
                                            {rec.indicativeEmi?.emi > 0 && (
                                                <div>
                                                    <div className="gov-fact-label">{tr(UI.monthlyEmi)}</div>
                                                    <div className="gov-fact-value">{formatInr(rec.indicativeEmi.emi)}</div>
                                                </div>
                                            )}
                                            <div>
                                                <div className="gov-fact-label">{tr(UI.rate)}</div>
                                                <div className="gov-fact-value">{rec.interestRate}%</div>
                                            </div>
                                        </div>
                                    )}

                                    {rec.costExceedsCap && (
                                        <div className="gov-notice gov-notice-warn" style={{ marginBottom: 10 }}>
                                            <HelpCircle size={15} /> <span>{tr(UI.costCapped)}</span>
                                        </div>
                                    )}

                                    {rec.failed?.length > 0 && (
                                        <>
                                            <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{tr(UI.whyNot)}</p>
                                            <ul className="gov-reason" style={{ paddingLeft: 18, marginTop: 0, marginBottom: 10 }}>
                                                {rec.failed.map((f, i) => <li key={i}>{tr(f)}</li>)}
                                            </ul>
                                        </>
                                    )}
                                    {rec.eligible && rec.matched?.length > 0 && (
                                        <ul className="gov-reason" style={{ paddingLeft: 18, marginTop: 0, marginBottom: 10 }}>
                                            {rec.matched.slice(0, 3).map((m, i) => <li key={i}>{tr(m)}</li>)}
                                        </ul>
                                    )}

                                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                        <Link to={`/credit-schemes/${rec.productId}`} className="gov-btn gov-btn-ghost gov-btn-sm">
                                            {tr(UI.viewScheme)}
                                        </Link>
                                        {rec.eligible && (
                                            <button className="gov-btn gov-btn-primary gov-btn-sm" onClick={() => onApply(rec)}>
                                                {tr(UI.applyNow)} <ArrowRight size={14} />
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))}

                            {(result.recommendations || []).length > 0 && (
                                <button className="gov-btn gov-btn-secondary gov-btn-sm" onClick={onSave}>
                                    {tr(UI.saveResults)}
                                </button>
                            )}
                        </>
                    )}
                </div>
            </section>

            <LoginPrompt open={!!prompt} onClose={() => setPrompt(null)} action={prompt?.action}>
                {prompt?.body}
            </LoginPrompt>
        </PublicPage>
    )
}
