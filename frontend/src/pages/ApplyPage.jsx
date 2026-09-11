import { useEffect, useMemo, useState } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import {
    ArrowLeft, ArrowRight, Loader2, MapPin, Navigation, ShieldCheck,
    CheckCircle2, AlertTriangle, FileCheck2, IndianRupee,
} from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { gateway } from '../lib/api'
import { getLocalUser } from '../lib/auth'
import { calculateEmi, formatInr, MORATORIUM_CAPITALISE, MORATORIUM_SERVICE_INTEREST } from '../lib/emiCalculator'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'
import './ApplyPage.css'

/**
 * The real, end-to-end credit application: details → EMI quote (created as a
 * DRAFT server-side) → choose a real branch → consent → submit.
 *
 * Three sources hand off here with a partial payload in `location.state`,
 * shaped like CreateApplicationRequest — {productId, estimatedCost,
 * annualIncome, category, tenureMonths, moratoriumMode, verificationMode}:
 * CreditSchemeDetailPage, EligibilityPage, and Sathi's application-assistant
 * chat flow. Whatever arrives pre-fills step 1 rather than skipping it — the
 * server is the source of truth for whether a draft is actually valid
 * (unit-cost band, tenure cap, mode availability), so the citizen always
 * confirms before anything is created.
 *
 * The 4 steps mirror the state machine CreditApplicationService actually
 * enforces: a DRAFT cannot be submitted without an assigned branch
 * (server refuses it — "otherwise there is no one to receive this
 * application"), and submitting requires PARTNER_SHARING consent, because
 * that is the moment a citizen's documents leave this platform for a bank.
 */
const STEPS = ['details', 'partner', 'consent', 'success']

const UI = {
    back: 'Back',
    loading: 'Loading…',
    notFound: 'That scheme could not be found.',
    loginTitle: 'Sign in to apply',
    loginBody: 'Applying creates a file we track for you, so it needs an account.',
    loginBtn: 'Sign in',

    stepDetails: 'Application details',
    stepPartner: 'Choose a branch',
    stepConsent: 'Consent & submit',
    stepDone: 'Submitted',

    prefillNote: 'Sathi already collected some of these details for you — check them before continuing.',
    estimatedCost: 'Project / course cost', estimatedCostHint: 'The total cost of what this loan is for.',
    annualIncome: 'Annual family income',
    category: 'Social category',
    selectOne: 'Select', catGeneral: 'General', catObc: 'OBC', catSc: 'SC', catSt: 'ST',
    tenure: 'Repayment period (months)', tenureHint: 'Up to',
    moratorium: 'How the moratorium is repaid',
    moratoriumCapitalise: 'Pay nothing at first — added to what you owe (costs more overall)',
    moratoriumService: 'Pay interest only at first — cheaper overall',
    verification: 'How your documents will be verified',
    modeManual: 'Upload documents, checked by the branch',
    modeOffline: 'Show documents in person at the branch',
    modeDigilocker: 'Fetch documents from DigiLocker',
    modeAccountAggregator: 'Verify income via Account Aggregator',
    modeUnavailable: '(not available in this deployment)',
    previewTitle: 'Your estimated EMI',
    previewLoan: 'Loan amount', previewMargin: 'Your contribution (margin money)',
    previewEmi: 'Monthly EMI', previewMonths: 'No EMI for the first',
    continueBtn: 'Continue', creating: 'Creating your application…',

    partnerIntro: 'Pick the real branch you want to apply through. The rate you actually pay depends on this choice.',
    findBranches: 'Find branches near me', gettingLocation: 'Getting your location…', findingBanks: 'Finding nearby banks…',
    denied: "Location access was blocked. Allow it in your browser's settings and try again.",
    lookupError: "Couldn't reach the branch lookup right now.",
    noBranches: 'No branches found nearby. Try again from somewhere closer to a town centre.',
    kmAway: 'km away',
    delivers: 'Confirmed for this scheme', unknownDelivers: 'Type not confirmed', cannotDeliver: "Can't process this scheme",
    choose: 'Apply through this branch', choosing: 'Confirming…',

    consentIntro: 'One last thing before this reaches a branch:',
    consentAgree: 'I agree', submit: 'Submit application', submitting: 'Submitting…',

    doneTitle: 'Application submitted',
    doneBody: 'Your application has been sent to the branch below. They will review it and may ask for documents.',
    doneId: 'Application ID', doneBranch: 'Branch', doneStatus: 'Status', doneEmi: 'Quoted EMI',
    doneSubmitted: 'Submitted',
    browseMore: 'Browse more schemes', goHome: 'Go to Home',
}

export default function ApplyPage() {
    const { schemeId } = useParams()
    const { state } = useLocation()
    const navigate = useNavigate()

    const [product, setProduct] = useState(null)
    const [productState, setProductState] = useState('loading') // loading | ready | missing | error
    const [step, setStep] = useState('details')
    const [error, setError] = useState('')

    const [application, setApplication] = useState(null)
    const [selectedPartner, setSelectedPartner] = useState(null)

    // Step 1 form — pre-filled from whatever the handoff already knew.
    const [form, setForm] = useState({
        estimatedCost: state?.estimatedCost ?? '',
        annualIncome: state?.annualIncome ?? '',
        category: state?.category ?? '',
        tenureMonths: '',
        moratoriumMode: state?.moratoriumMode || MORATORIUM_CAPITALISE,
        verificationMode: state?.verificationMode || 'manual',
    })
    const [creating, setCreating] = useState(false)

    const [verifyAvailable, setVerifyAvailable] = useState(false)

    useEffect(() => {
        const productId = state?.productId || schemeId
        gateway.creditProducts()
            .then((list) => {
                const found = (Array.isArray(list) ? list : [])
                    .find((p) => p.id === productId || p.code === productId)
                setProduct(found || null)
                setProductState(found ? 'ready' : 'missing')
                if (found) {
                    setForm((f) => ({ ...f, tenureMonths: f.tenureMonths || found.maxTenureMonths }))
                }
            })
            .catch(() => setProductState('error'))
        // Same flag gates DigiLocker and Account Aggregator as a selectable
        // verification mode server-side (app.demo.simulate-integrations) —
        // this profile-scoped status call already reports it.
        gateway.digilockerStatus().then((s) => setVerifyAvailable(!!s.available)).catch(() => {})
    }, [schemeId, state?.productId])

    const guest = !getLocalUser()

    const preview = useMemo(() => {
        if (!product || !form.estimatedCost) return null
        const cost = Number(form.estimatedCost)
        if (!cost || cost <= 0) return null
        const covered = Math.round(cost * (product.coveragePct / 100))
        const loanAmount = Math.min(covered, product.maxLoanAmount)
        const tenure = Number(form.tenureMonths) || product.maxTenureMonths
        const emi = calculateEmi(loanAmount, product.interestRate, tenure, {
            moratoriumMonths: product.moratoriumMonths,
            moratoriumMode: form.moratoriumMode,
        })
        return { loanAmount, marginMoney: cost - loanAmount, tenure, emi }
    }, [product, form.estimatedCost, form.tenureMonths, form.moratoriumMode])

    const tr = useAutoTranslate([
        ...Object.values(UI),
        product?.name, product?.description,
    ].filter(Boolean))

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

    const submitDetails = async (e) => {
        e.preventDefault()
        setError(''); setCreating(true)
        try {
            const created = await gateway.createCreditApplication({
                productId: product.id,
                estimatedCost: Number(form.estimatedCost),
                annualIncome: form.annualIncome ? Number(form.annualIncome) : null,
                category: form.category || null,
                tenureMonths: Number(form.tenureMonths) || product.maxTenureMonths,
                moratoriumMode: form.moratoriumMode,
                verificationMode: form.verificationMode,
            })
            setApplication(created)
            setStep('partner')
        } catch (err) {
            setError(err.message)
        } finally {
            setCreating(false)
        }
    }

    if (guest) {
        return (
            <div className="page-wrapper">
                <Navbar />
                <main className="page-content" style={{ maxWidth: 480, margin: '0 auto', padding: '24px 16px' }}>
                    <div className="glass-card" style={{ padding: 24, textAlign: 'center' }}>
                        <ShieldCheck size={28} className="text-saffron" style={{ marginBottom: 10 }} />
                        <h2 style={{ marginBottom: 8 }}>{tr(UI.loginTitle)}</h2>
                        <p className="text-subtle" style={{ marginBottom: 16 }}>{tr(UI.loginBody)}</p>
                        <button className="btn btn-primary"
                            onClick={() => navigate('/signin', { state: { from: `/apply/${schemeId}` } })}>
                            {tr(UI.loginBtn)}
                        </button>
                    </div>
                </main>
                <BottomNav />
            </div>
        )
    }

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content" style={{ maxWidth: 560, margin: '0 auto', padding: '24px 16px' }}>
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)} style={{ marginBottom: 14 }}>
                    <ArrowLeft size={16} /> {tr(UI.back)}
                </button>

                {productState === 'loading' && (
                    <div className="glass-card" style={{ padding: 24, textAlign: 'center' }}>
                        <Loader2 size={22} className="spin text-saffron" />
                        <p className="text-subtle" style={{ marginTop: 8 }}>{tr(UI.loading)}</p>
                    </div>
                )}
                {(productState === 'missing' || productState === 'error') && (
                    <div className="glass-card" style={{ padding: 24, textAlign: 'center' }}>
                        <AlertTriangle size={22} className="text-saffron" />
                        <p style={{ marginTop: 8 }}>{tr(UI.notFound)}</p>
                    </div>
                )}

                {productState === 'ready' && product && (
                    <>
                        <StepIndicator step={step} tr={tr} />
                        <h2 style={{ margin: '6px 0 2px' }}>{tr(product.name)}</h2>
                        <p className="text-subtle" style={{ fontSize: 13, marginBottom: 16 }}>{product.code} · {product.interestRate}%</p>

                        {step === 'details' && (
                            <DetailsStep
                                product={product} form={form} set={set} preview={preview} tr={tr}
                                hadPrefill={!!state?.productId} error={error} creating={creating}
                                verifyAvailable={verifyAvailable} onSubmit={submitDetails}
                            />
                        )}
                        {step === 'partner' && application && (
                            <PartnerStep
                                product={product} application={application} tr={tr}
                                onChosen={(app, partner) => { setApplication(app); setSelectedPartner(partner); setStep('consent') }}
                            />
                        )}
                        {step === 'consent' && application && (
                            <ConsentStep
                                application={application} tr={tr}
                                onSubmitted={(app) => { setApplication(app); setStep('success') }}
                            />
                        )}
                        {step === 'success' && application && (
                            <SuccessStep application={application} partner={selectedPartner} tr={tr} navigate={navigate} />
                        )}
                    </>
                )}
            </main>
            <BottomNav />
        </div>
    )
}

function StepIndicator({ step, tr }) {
    const idx = STEPS.indexOf(step)
    const labels = [UI.stepDetails, UI.stepPartner, UI.stepConsent, UI.stepDone]
    return (
        <div className="apply-steps">
            {labels.map((label, i) => (
                <div key={label} className={`apply-step ${i < idx ? 'done' : i === idx ? 'active' : ''}`}>
                    <span className="apply-step-dot">{i < idx ? <CheckCircle2 size={13} /> : i + 1}</span>
                    <span className="apply-step-label">{tr(label)}</span>
                </div>
            ))}
        </div>
    )
}

function DetailsStep({ product, form, set, preview, tr, hadPrefill, error, creating, verifyAvailable, onSubmit }) {
    return (
        <form className="glass-card apply-form" onSubmit={onSubmit}>
            {hadPrefill && <p className="apply-prefill-note">{tr(UI.prefillNote)}</p>}

            <label>{tr(UI.estimatedCost)}
                <input className="input-glass" type="number" inputMode="numeric" required
                    value={form.estimatedCost} onChange={set('estimatedCost')} />
                <span className="apply-field-hint">{tr(UI.estimatedCostHint)}</span>
            </label>

            <label>{tr(UI.annualIncome)}
                <input className="input-glass" type="number" inputMode="numeric" value={form.annualIncome} onChange={set('annualIncome')} />
            </label>

            <label>{tr(UI.category)}
                <select className="input-glass" value={form.category} onChange={set('category')}>
                    <option value="">{tr(UI.selectOne)}</option>
                    <option value="sc">{tr(UI.catSc)}</option>
                    <option value="st">{tr(UI.catSt)}</option>
                    <option value="obc">{tr(UI.catObc)}</option>
                    <option value="general">{tr(UI.catGeneral)}</option>
                </select>
            </label>

            <label>{tr(UI.tenure)}
                <input className="input-glass" type="number" inputMode="numeric" min={1} max={product.maxTenureMonths}
                    value={form.tenureMonths} onChange={set('tenureMonths')} />
                <span className="apply-field-hint">{tr(UI.tenureHint)} {product.maxTenureMonths}</span>
            </label>

            <label>{tr(UI.moratorium)}
                <select className="input-glass" value={form.moratoriumMode} onChange={set('moratoriumMode')}>
                    <option value={MORATORIUM_CAPITALISE}>{tr(UI.moratoriumCapitalise)}</option>
                    <option value={MORATORIUM_SERVICE_INTEREST}>{tr(UI.moratoriumService)}</option>
                </select>
            </label>

            <label>{tr(UI.verification)}
                <select className="input-glass" value={form.verificationMode} onChange={set('verificationMode')}>
                    <option value="manual">{tr(UI.modeManual)}</option>
                    <option value="offline">{tr(UI.modeOffline)}</option>
                    <option value="digilocker" disabled={!verifyAvailable}>
                        {tr(UI.modeDigilocker)}{!verifyAvailable ? ` ${tr(UI.modeUnavailable)}` : ''}
                    </option>
                    <option value="account_aggregator" disabled={!verifyAvailable}>
                        {tr(UI.modeAccountAggregator)}{!verifyAvailable ? ` ${tr(UI.modeUnavailable)}` : ''}
                    </option>
                </select>
            </label>

            {preview && (
                <div className="apply-preview">
                    <h4><IndianRupee size={14} style={{ verticalAlign: '-2px' }} /> {tr(UI.previewTitle)}</h4>
                    <div className="apply-preview-row"><span>{tr(UI.previewLoan)}</span><strong>{formatInr(preview.loanAmount)}</strong></div>
                    <div className="apply-preview-row"><span>{tr(UI.previewMargin)}</span><strong>{formatInr(preview.marginMoney)}</strong></div>
                    <div className="apply-preview-row"><span>{tr(UI.previewEmi)}</span><strong>{formatInr(preview.emi.emi)}</strong></div>
                    {product.moratoriumMonths > 0 && (
                        <p className="apply-field-hint">{tr(UI.previewMonths)} {product.moratoriumMonths} months.</p>
                    )}
                </div>
            )}

            {error && <p className="apply-error">{error}</p>}

            <button className="btn btn-primary" type="submit" disabled={creating}>
                {creating ? <><Loader2 size={15} className="spin" /> {tr(UI.creating)}</> : <>{tr(UI.continueBtn)} <ArrowRight size={15} /></>}
            </button>
        </form>
    )
}

function PartnerStep({ product, application, tr, onChosen }) {
    const [locStatus, setLocStatus] = useState('idle') // idle | enabling | denied
    const [loadStatus, setLoadStatus] = useState('idle') // idle | loading | done | error
    const [partners, setPartners] = useState([])
    const [choosingId, setChoosingId] = useState(null)
    const [error, setError] = useState('')

    const findBranches = () => {
        if (!navigator.geolocation) { setLocStatus('denied'); return }
        setLocStatus('enabling')
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                setLocStatus('idle'); setLoadStatus('loading')
                try {
                    const res = await gateway.creditPartnersNearby(pos.coords.latitude, pos.coords.longitude, 15, product.id)
                    setPartners(res.partners || [])
                    setLoadStatus('done')
                } catch {
                    setLoadStatus('error')
                }
            },
            () => setLocStatus('denied'),
            { enableHighAccuracy: true, timeout: 10000 },
        )
    }

    const choose = async (p) => {
        const partnerId = `${p.name}-${p.lat}-${p.lng}`
        setChoosingId(partnerId); setError('')
        try {
            const updated = await gateway.chooseCreditPartner(application.id, {
                partnerId, partnerName: p.name, partnerType: p.type,
            })
            onChosen(updated, p)
        } catch (err) {
            setError(err.message)
        } finally {
            setChoosingId(null)
        }
    }

    const busy = locStatus === 'enabling' || loadStatus === 'loading'

    return (
        <div className="glass-card apply-form">
            <p className="apply-prefill-note">{tr(UI.partnerIntro)}</p>

            {loadStatus !== 'done' && (
                <button className="btn btn-primary" onClick={findBranches} disabled={busy}>
                    {busy ? <Loader2 size={15} className="spin" /> : <MapPin size={15} />}
                    {locStatus === 'enabling' ? tr(UI.gettingLocation) : loadStatus === 'loading' ? tr(UI.findingBanks) : tr(UI.findBranches)}
                </button>
            )}
            {locStatus === 'denied' && <p className="apply-error">{tr(UI.denied)}</p>}
            {loadStatus === 'error' && <p className="apply-error">{tr(UI.lookupError)}</p>}
            {loadStatus === 'done' && partners.length === 0 && <p className="text-subtle">{tr(UI.noBranches)}</p>}
            {error && <p className="apply-error">{error}</p>}

            {partners.map((p) => {
                const partnerId = `${p.name}-${p.lat}-${p.lng}`
                const cannotDeliver = p.deliversScheme === false
                return (
                    <div key={partnerId} className={`apply-partner-card ${cannotDeliver ? 'disabled' : ''}`}>
                        <div>
                            <strong>{p.name}</strong>
                            <div className="apply-field-hint">
                                {p.type} · {p.distanceKm != null ? `${p.distanceKm.toFixed(1)} ${tr(UI.kmAway)}` : ''}
                            </div>
                            {p.deliversScheme === true && <span className="badge badge-green" style={{ marginTop: 4 }}><FileCheck2 size={11} /> {tr(UI.delivers)}</span>}
                            {p.deliversScheme === null && <span className="badge badge-muted" style={{ marginTop: 4 }}>{tr(UI.unknownDelivers)}</span>}
                            {cannotDeliver && <span className="badge badge-red" style={{ marginTop: 4 }}>{tr(UI.cannotDeliver)}</span>}
                        </div>
                        <div style={{ display: 'flex', gap: 8 }}>
                            <a href={`https://maps.google.com/?q=${p.lat},${p.lng}`} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
                                <Navigation size={13} />
                            </a>
                            <button className="btn btn-primary btn-sm" disabled={cannotDeliver || choosingId === partnerId}
                                onClick={() => choose(p)}>
                                {choosingId === partnerId ? tr(UI.choosing) : tr(UI.choose)}
                            </button>
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

function ConsentStep({ application, tr, onSubmitted }) {
    const [statement, setStatement] = useState(
        'I agree that my application and the documents I upload may be shared with the Channel Partner branch I have chosen, so that they can process my loan.',
    )
    const [agreed, setAgreed] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState('')

    useEffect(() => {
        // Fetched, not hardcoded, so the checkbox always matches whatever
        // ConsentService actually stores if the wording is ever updated —
        // the fallback above is just so the page isn't blank while this loads.
        gateway.consentPurposes()
            .then((list) => {
                const found = (list || []).find((p) => p.purpose === 'partner_sharing')
                if (found) setStatement(found.statement)
            })
            .catch(() => {})
    }, [])

    const submit = async () => {
        setSubmitting(true); setError('')
        try {
            await gateway.grantConsent('partner_sharing', application.id)
            const submitted = await gateway.submitCreditApplication(application.id)
            onSubmitted(submitted)
        } catch (err) {
            setError(err.message)
        } finally {
            setSubmitting(false)
        }
    }

    return (
        <div className="glass-card apply-form">
            <p className="apply-prefill-note">{tr(UI.consentIntro)}</p>
            <label className="apply-check">
                <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
                {tr(statement)}
            </label>
            {error && <p className="apply-error">{error}</p>}
            <button className="btn btn-primary" disabled={!agreed || submitting} onClick={submit}>
                {submitting ? <><Loader2 size={15} className="spin" /> {tr(UI.submitting)}</> : tr(UI.submit)}
            </button>
        </div>
    )
}

function SuccessStep({ application, partner, tr, navigate }) {
    const terms = application.quotedTerms
    return (
        <div className="glass-card apply-form" style={{ textAlign: 'center' }}>
            <CheckCircle2 size={32} className="text-green" style={{ marginBottom: 8 }} />
            <h3>{tr(UI.doneTitle)}</h3>
            <p className="text-subtle" style={{ marginBottom: 16 }}>{tr(UI.doneBody)}</p>

            <div style={{ textAlign: 'left' }}>
                <div className="apply-preview-row"><span>{tr(UI.doneId)}</span><strong>#{application.id.slice(0, 8)}</strong></div>
                <div className="apply-preview-row"><span>{tr(UI.doneBranch)}</span><strong>{partner?.name || application.assignedPartnerName}</strong></div>
                <div className="apply-preview-row"><span>{tr(UI.doneStatus)}</span><span className="badge badge-saffron">{tr(UI.doneSubmitted)}</span></div>
                {terms && <div className="apply-preview-row"><span>{tr(UI.doneEmi)}</span><strong>{formatInr(terms.emi)}</strong></div>}
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 18 }}>
                <button className="btn btn-ghost" onClick={() => navigate('/credit-schemes')}>{tr(UI.browseMore)}</button>
                <button className="btn btn-primary" onClick={() => navigate('/home')}>{tr(UI.goHome)}</button>
            </div>
        </div>
    )
}
