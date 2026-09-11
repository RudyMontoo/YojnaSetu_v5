import { useEffect, useMemo, useState } from 'react'
import { Calculator, Info } from 'lucide-react'
import { PublicPage } from '../../components/PublicShell'
import LoginPrompt from '../../components/LoginPrompt'
import { isGuest } from '../../lib/auth'
import { gateway } from '../../lib/api'
import {
    calculateEmi, formatInr,
    MORATORIUM_CAPITALISE, MORATORIUM_SERVICE_INTEREST,
} from '../../lib/emiCalculator'
import { useAutoTranslate } from '../../lib/i18n'
import './PublicPages.css'

const UI = {
    title: 'EMI calculator',
    sub: 'Work out your monthly repayment before you apply. Nothing here needs an account.',
    scheme: 'Scheme',
    schemeHint: 'Picking a scheme fills in its real interest rate, moratorium and maximum tenure.',
    custom: 'Custom (enter my own figures)',
    amount: 'Loan amount',
    amountOver: 'This is above the scheme maximum of',
    rate: 'Interest rate (% per year)',
    tenure: 'Repayment period (months)',
    tenureHint: 'Counted after the EMI-free months below.',
    moratorium: 'EMI-free months at the start',
    moratoriumHint: 'Most NSFDC schemes let you start repaying a few months after the loan is given.',
    duringTitle: 'During those EMI-free months',
    modeCapitalise: 'Pay nothing now (interest is added to the loan)',
    modeService: 'Pay just the interest each month',
    resultsTitle: 'Your repayment',
    monthlyEmi: 'Monthly EMI',
    totalInterest: 'Total interest',
    totalPayment: 'Total you repay',
    duringMoratorium: 'Interest during the EMI-free months',
    financedNote: 'Interest builds up during the EMI-free months, so the amount you repay EMIs on is',
    servicedNote: 'Paying the interest monthly keeps your loan amount unchanged.',
    schedule: 'Month-by-month schedule',
    colMonth: 'Month', colEmi: 'EMI', colPrincipal: 'Principal', colInterest: 'Interest', colBalance: 'Balance',
    phaseMoratorium: 'EMI-free',
    save: 'Save this calculation',
    loginToSave: 'save this calculation',
    loginSaveBody: 'Create an account to keep this calculation and attach it to an application later.',
    noLogin: 'No login needed',
}

export default function EmiCalculatorPage() {
    const [products, setProducts] = useState([])
    const [schemeId, setSchemeId] = useState('custom')
    const [amount, setAmount] = useState(125000)
    const [rate, setRate] = useState(6.5)
    const [tenure, setTenure] = useState(36)
    const [moratorium, setMoratorium] = useState(3)
    const [mode, setMode] = useState(MORATORIUM_CAPITALISE)
    const [prompt, setPrompt] = useState(false)

    useEffect(() => {
        gateway.creditProducts()
            .then((list) => setProducts(Array.isArray(list) ? list : []))
            .catch(() => {})
    }, [])

    const scheme = products.find((p) => p.id === schemeId) || null

    const applyScheme = (id) => {
        setSchemeId(id)
        const p = products.find((x) => x.id === id)
        if (!p) return
        // Seed the form from the scheme's REAL terms, so the default a citizen
        // sees is one this scheme would actually offer.
        setRate(p.interestRate)
        setMoratorium(p.moratoriumMonths)
        setTenure(p.maxTenureMonths)
        setAmount(Math.min(Number(amount) || p.maxLoanAmount, p.maxLoanAmount))
    }

    const plan = useMemo(
        () => calculateEmi(amount, rate, tenure, { moratoriumMonths: moratorium, moratoriumMode: mode }),
        [amount, rate, tenure, moratorium, mode]
    )

    const overCap = scheme && Number(amount) > scheme.maxLoanAmount

    const tr = useAutoTranslate([...Object.values(UI), ...products.map((p) => p.name)])

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
                    <div className="gov-card" style={{ marginBottom: 18 }}>
                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.scheme)}</span>
                            <select className="gov-select" value={schemeId} onChange={(e) => applyScheme(e.target.value)}>
                                <option value="custom">{tr(UI.custom)}</option>
                                {products.map((p) => (
                                    <option key={p.id} value={p.id}>{tr(p.name)} — {p.interestRate}%</option>
                                ))}
                            </select>
                            <span className="gov-hint">{tr(UI.schemeHint)}</span>
                        </label>

                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.amount)}</span>
                            <input className="gov-input" inputMode="numeric" value={amount}
                                onChange={(e) => setAmount(Number(e.target.value.replace(/[^0-9]/g, '')) || 0)} />
                            {overCap && (
                                <span className="gov-hint" style={{ color: 'var(--gov-amber)' }}>
                                    {tr(UI.amountOver)} {formatInr(scheme.maxLoanAmount)}.
                                </span>
                            )}
                        </label>

                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.rate)}</span>
                            <input className="gov-input" inputMode="decimal" value={rate}
                                onChange={(e) => setRate(Number(e.target.value.replace(/[^0-9.]/g, '')) || 0)} />
                        </label>

                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.tenure)}</span>
                            <input className="gov-input" inputMode="numeric" value={tenure}
                                onChange={(e) => setTenure(Number(e.target.value.replace(/[^0-9]/g, '')) || 1)} />
                            <span className="gov-hint">{tr(UI.tenureHint)}</span>
                        </label>

                        <label className="gov-field">
                            <span className="gov-label">{tr(UI.moratorium)}</span>
                            <input className="gov-input" inputMode="numeric" value={moratorium}
                                onChange={(e) => setMoratorium(Number(e.target.value.replace(/[^0-9]/g, '')) || 0)} />
                            <span className="gov-hint">{tr(UI.moratoriumHint)}</span>
                        </label>

                        {moratorium > 0 && (
                            <div className="gov-field" style={{ marginBottom: 0 }}>
                                <span className="gov-label">{tr(UI.duringTitle)}</span>
                                <div className="gov-radio-row">
                                    {[[MORATORIUM_CAPITALISE, UI.modeCapitalise], [MORATORIUM_SERVICE_INTEREST, UI.modeService]].map(([val, label]) => (
                                        <label key={val} className={`gov-radio ${mode === val ? 'active' : ''}`}>
                                            <input type="radio" name="mode" checked={mode === val} onChange={() => setMode(val)} />
                                            {tr(label)}
                                        </label>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="gov-card" style={{ marginBottom: 18 }}>
                        <h2 className="gov-section-title" style={{ fontSize: 17, marginBottom: 14 }}>
                            <Calculator size={17} style={{ verticalAlign: '-3px' }} /> {tr(UI.resultsTitle)}
                        </h2>
                        <div className="gov-facts">
                            <div>
                                <div className="gov-fact-label">{tr(UI.monthlyEmi)}</div>
                                <div className="gov-fact-value" style={{ fontSize: 22 }}>{formatInr(plan.emi)}</div>
                            </div>
                            <div>
                                <div className="gov-fact-label">{tr(UI.totalInterest)}</div>
                                <div className="gov-fact-value">{formatInr(plan.totalInterest)}</div>
                            </div>
                            <div>
                                <div className="gov-fact-label">{tr(UI.totalPayment)}</div>
                                <div className="gov-fact-value">{formatInr(plan.totalPayment)}</div>
                            </div>
                            {moratorium > 0 && (
                                <div>
                                    <div className="gov-fact-label">{tr(UI.duringMoratorium)}</div>
                                    <div className="gov-fact-value">{formatInr(plan.moratoriumInterest)}</div>
                                </div>
                            )}
                        </div>

                        {moratorium > 0 && (
                            <div className="gov-notice gov-notice-info" style={{ marginTop: 14 }}>
                                <Info size={16} />
                                <span>
                                    {mode === MORATORIUM_CAPITALISE
                                        ? <>{tr(UI.financedNote)} <strong>{formatInr(plan.financedPrincipal)}</strong>.</>
                                        : tr(UI.servicedNote)}
                                </span>
                            </div>
                        )}

                        <button className="gov-btn gov-btn-secondary gov-btn-sm" style={{ marginTop: 14 }}
                            onClick={() => { if (isGuest()) setPrompt(true) }}>
                            {tr(UI.save)}
                        </button>
                    </div>

                    <details className="gov-card">
                        <summary style={{ cursor: 'pointer', fontWeight: 600, color: 'var(--gov-ink)' }}>
                            {tr(UI.schedule)}
                        </summary>
                        <div style={{ overflowX: 'auto', marginTop: 14 }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                                <thead>
                                    <tr>
                                        {[UI.colMonth, UI.colEmi, UI.colPrincipal, UI.colInterest, UI.colBalance].map((h) => (
                                            <th key={h} style={{ textAlign: 'left', padding: '8px 10px', borderBottom: '1px solid var(--gov-line)', color: 'var(--gov-muted)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                                                {tr(h)}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {plan.schedule.map((row) => (
                                        <tr key={row.month}>
                                            <td style={{ padding: '7px 10px', borderBottom: '1px solid var(--gov-line)', whiteSpace: 'nowrap' }}>
                                                {row.month}
                                                {row.month <= moratorium && (
                                                    <span className="gov-badge gov-badge-muted" style={{ marginLeft: 6 }}>{tr(UI.phaseMoratorium)}</span>
                                                )}
                                            </td>
                                            <td style={{ padding: '7px 10px', borderBottom: '1px solid var(--gov-line)' }}>{formatInr(row.emi)}</td>
                                            <td style={{ padding: '7px 10px', borderBottom: '1px solid var(--gov-line)' }}>{formatInr(row.principalComponent)}</td>
                                            <td style={{ padding: '7px 10px', borderBottom: '1px solid var(--gov-line)' }}>{formatInr(row.interestComponent)}</td>
                                            <td style={{ padding: '7px 10px', borderBottom: '1px solid var(--gov-line)' }}>{formatInr(row.balance)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </details>
                </div>
            </section>

            <LoginPrompt open={prompt} onClose={() => setPrompt(false)} action={tr(UI.loginToSave)}>
                {tr(UI.loginSaveBody)}
            </LoginPrompt>
        </PublicPage>
    )
}
