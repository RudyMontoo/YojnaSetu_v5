import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft, CheckCircle, XCircle, ExternalLink, MapPin, FileText, Zap, Eye, Loader2 } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import ApplyMethodModal from '../components/ApplyMethodModal'
import { ai } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'
import './SchemeDetailPage.css'

// Static labels — live-translated alongside the scheme content.
const UI = {
    back: 'Back', schemes: 'Schemes', keyBenefit: 'Key Benefit:',
    eligNote: '✅ = You likely qualify  |  ? = Verify on official portal',
    applyNow: 'Apply Now', offlineHelp: 'Get Offline Help',
    seeLiveForm: 'See the live application form',
    checkingForm: 'Checking the official portal…',
    liveFormTitle: 'What the official form asks right now',
    liveFormFields: 'Form fields on the portal:',
    liveFormDocs: 'Documents the portal mentions:',
    required: 'required',
    reconUnavailable: "Couldn't read the live form (the portal may load its form with JavaScript). Follow the steps above or use a CSC.",
}
const APPLY_STEPS = [
    'Visit Jan Seva Kendra (CSC) or the official portal',
    'Fill out the application form and provide required documents',
    'Submit the form — you will receive an Application ID',
    'Track status under "My Applications"',
]

const SCHEMES_DATA = {
    'pm-kisan': {
        name: 'Pradhan Mantri Kisan Samman Nidhi',
        shortName: 'PM-Kisan',
        ministry: 'Ministry of Agriculture',
        category: 'Agriculture',
        tag: 'Central',
        icon: '🌾',
        benefit: '₹6,000 per year in 3 equal instalments of ₹2,000 each',
        overview: 'PM-KISAN is a Central Sector scheme with 100% funding from Government of India. Under this scheme, income support of ₹6000/- per year is provided to all farmer families across the country in three equal installments of ₹2000/- each every four months.',
        eligibility: [
            { text: 'Must be a farmer / cultivator family', pass: true },
            { text: 'Must own cultivable land in your name', pass: true },
            { text: 'Annual income below ₹1.5 Lakh', pass: true },
            { text: 'Should not be a government employee', pass: null },
            { text: 'Should not be an income tax payee', pass: null },
        ],
        documents: [
            'Aadhaar Card (mandatory for eKYC)',
            'Land ownership records (Khasra/Khatauni)',
            'Bank account details linked to Aadhaar',
            'Latest photograph (passport size)',
            'Mobile number linked to Aadhaar',
        ],
        applyUrl: 'https://pmkisan.gov.in',
        applyPortal: 'PM-Kisan Portal',
    },
    'pm-awas': {
        name: 'Pradhan Mantri Awas Yojana (Gramin)',
        shortName: 'PMAY-G',
        ministry: 'Ministry of Rural Development',
        category: 'Housing',
        tag: 'Central',
        icon: '🏠',
        benefit: 'Financial assistance of ₹1.20 Lakh (plain) / ₹1.30 Lakh (hilly) for construction of a pucca house',
        overview: 'Under PMAY-G, financial assistance is provided for construction of pucca houses to all houseless and those living in dilapidated houses. The houses are constructed on the basis of demand by the beneficiaries and funds are directly transferred to their bank accounts.',
        eligibility: [
            { text: 'Must belong to rural area', pass: true },
            { text: 'Must be houseless or live in kutcha/dilapidated house', pass: null },
            { text: 'Name in SECC 2011 Survey list', pass: null },
            { text: 'Should not own a pucca house anywhere in India', pass: null },
        ],
        documents: [
            'Aadhaar Card',
            'Bank account details',
            'BPL certificate / SECC 2011 data',
            'Job card (if MGNREGA beneficiary)',
            'Land documents',
        ],
        applyUrl: 'https://pmayg.nic.in',
        applyPortal: 'PMAY-G Portal',
    },
}

const DEFAULT_SCHEME = {
    name: 'Government Scheme', shortName: 'Scheme', ministry: 'Government of India',
    category: 'General', tag: 'Central', icon: '📋',
    benefit: 'Benefits available. Click "Apply Now" to learn more.',
    overview: 'This scheme provides essential benefits to eligible citizens.',
    eligibility: [{ text: 'Check official portal for eligibility', pass: null }],
    documents: ['Aadhaar Card', 'Bank Account Details', 'Photograph'],
    applyUrl: 'https://india.gov.in', applyPortal: 'India.gov.in',
}

const TABS = ['Overview', 'Eligibility', 'Documents', 'How to Apply']

export default function SchemeDetailPage() {
    const { id } = useParams()
    const navigate = useNavigate()
    const location = useLocation()
    const [activeTab, setActiveTab] = useState('Overview')
    const [showApplyModal, setShowApplyModal] = useState(false)
    const [recon, setRecon] = useState(null)        // Agent 3 live portal recon result
    const [reconBusy, setReconBusy] = useState(false)

    const runRecon = async () => {
        setReconBusy(true)
        try { setRecon(await ai.portalRecon(id)) }
        catch { setRecon({ error: true }) }
        finally { setReconBusy(false) }
    }

    // Priority: router state (from chat/agent) > hardcoded dict > default
    const routeState = location.state  // passed by ChatPage navigate()
    const hardcoded = SCHEMES_DATA[id]

    const scheme = hardcoded || {
        ...DEFAULT_SCHEME,
        // Use real data from route state if available
        ...(routeState ? {
            name: routeState.name || id?.replace(/-/g, ' '),
            shortName: routeState.name?.split(' ').slice(0, 2).join(' ') || 'Scheme',
            ministry: routeState.state ? `Government of ${routeState.state}` : 'Government of India',
            category: routeState.sector || 'General',
            tag: routeState.state === 'Central' ? 'Central' : (routeState.state || 'Central'),
            benefit: routeState.benefit || DEFAULT_SCHEME.benefit,
            applyUrl: routeState.apply_url || DEFAULT_SCHEME.applyUrl,
            applyPortal: (() => { try { return new URL(routeState.apply_url).hostname } catch { return DEFAULT_SCHEME.applyPortal } })(),
        } : {
            name: id?.replace(/-/g, ' ') || 'Government Scheme',
        }),
    }

    // Live-translate everything on the page: the scheme's own text (name,
    // ministry, benefit, overview, eligibility, documents) plus all fixed
    // labels, tabs, and apply steps.
    const tr = useAutoTranslate([
        ...Object.values(UI), ...TABS, ...APPLY_STEPS,
        scheme.name, scheme.shortName, scheme.ministry, scheme.category,
        scheme.tag, scheme.benefit, scheme.overview,
        ...(scheme.eligibility?.map(e => e.text) || []),
        ...(scheme.documents || []),
        // live recon field/doc labels (from the real portal) so they translate too
        ...((recon?.recon?.forms || []).flatMap(f => f.fields).map(f => f.label)),
        ...(recon?.recon?.document_hints || []),
    ])

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                {/* Breadcrumb */}
                <div className="detail-breadcrumb">
                    <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>
                        <ArrowLeft size={14} /> {tr(UI.back)}
                    </button>
                    <span className="text-subtle">{tr(UI.schemes)} / {tr(scheme.shortName)}</span>
                </div>

                {/* Hero */}
                <div className="glass-card detail-hero">
                    <div className="detail-hero-icon">{scheme.icon}</div>
                    <div className="detail-hero-info">
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                            <span className="badge badge-saffron">{tr(scheme.category)}</span>
                            <span className="badge badge-muted">{tr(scheme.tag)}</span>
                        </div>
                        <h1 className="detail-title">{tr(scheme.name)}</h1>
                        <p className="text-muted detail-ministry">{tr(scheme.ministry)}</p>
                    </div>
                </div>

                {/* Benefit highlight */}
                <div className="detail-benefit-card glass-card">
                    <span className="detail-benefit-label text-muted">{tr(UI.keyBenefit)}</span>
                    <p className="detail-benefit-text text-saffron">{tr(scheme.benefit)}</p>
                </div>

                {/* Tabs */}
                <div className="detail-tabs">
                    {TABS.map(tab => (
                        <button key={tab} className={`chip ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>
                            {tr(tab)}
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="glass-card detail-tab-content">

                    {activeTab === 'Overview' && (
                        <p className="detail-overview-text">{tr(scheme.overview)}</p>
                    )}

                    {activeTab === 'Eligibility' && (
                        <div className="detail-eligibility-list">
                            {scheme.eligibility.map((item, i) => (
                                <div key={i} className="detail-elig-item">
                                    {item.pass === true ? (
                                        <CheckCircle size={18} className="text-green" />
                                    ) : item.pass === false ? (
                                        <XCircle size={18} className="text-red" />
                                    ) : (
                                        <div className="elig-unknown">?</div>
                                    )}
                                    <span className="detail-elig-text">{tr(item.text)}</span>
                                </div>
                            ))}
                            <p className="text-muted detail-elig-note">
                                {tr(UI.eligNote)}
                            </p>
                        </div>
                    )}

                    {activeTab === 'Documents' && (
                        <ol className="detail-docs-list">
                            {scheme.documents.map((doc, i) => (
                                <li key={i} className="detail-doc-item">
                                    <div className="detail-doc-num">{i + 1}</div>
                                    <FileText size={16} className="text-saffron" />
                                    <span>{tr(doc)}</span>
                                </li>
                            ))}
                        </ol>
                    )}

                    {activeTab === 'How to Apply' && (
                        <div className="detail-apply-steps">
                            {APPLY_STEPS.map((step, i) => (
                                <div key={i} className="detail-apply-step">
                                    <div className="detail-step-num">{i + 1}</div>
                                    <p>{tr(step)}</p>
                                </div>
                            ))}

                            {/* Agent 3 — read-only live portal recon. Reads the real
                                government form so the citizen knows what to prepare. */}
                            <div style={{ marginTop: 16 }}>
                                {!recon && (
                                    <button className="btn btn-ghost btn-sm" onClick={runRecon} disabled={reconBusy}>
                                        {reconBusy ? <Loader2 size={14} className="spin" /> : <Eye size={14} />}
                                        {' '}{tr(reconBusy ? UI.checkingForm : UI.seeLiveForm)}
                                    </button>
                                )}
                                {recon && (() => {
                                    const r = recon.recon
                                    const fields = r?.forms?.flatMap(f => f.fields) || []
                                    const docs = r?.document_hints || []
                                    if (recon.error || !r || (!fields.length && !docs.length)) {
                                        return <p className="text-muted" style={{ fontSize: 13 }}>{tr(UI.reconUnavailable)}</p>
                                    }
                                    return (
                                        <div className="glass-card" style={{ padding: 14, marginTop: 6 }}>
                                            <p className="profile-app-name" style={{ marginBottom: 8 }}>
                                                <Eye size={14} className="text-saffron" style={{ verticalAlign: -2, marginRight: 5 }} />
                                                {tr(UI.liveFormTitle)}
                                            </p>
                                            {fields.length > 0 && <>
                                                <p className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>{tr(UI.liveFormFields)}</p>
                                                <ul style={{ margin: '0 0 10px 16px', fontSize: 13 }}>
                                                    {fields.slice(0, 12).map((f, i) => (
                                                        <li key={i}>{tr(f.label)}{f.required && <span className="text-saffron"> ({tr(UI.required)})</span>}</li>
                                                    ))}
                                                </ul>
                                            </>}
                                            {docs.length > 0 && <>
                                                <p className="text-muted" style={{ fontSize: 12, marginBottom: 4 }}>{tr(UI.liveFormDocs)}</p>
                                                <ul style={{ margin: '0 0 0 16px', fontSize: 13 }}>
                                                    {docs.slice(0, 8).map((d, i) => <li key={i}>{tr(d)}</li>)}
                                                </ul>
                                            </>}
                                        </div>
                                    )
                                })()}
                            </div>
                        </div>
                    )}
                </div>

                {/* CTA Buttons */}
                <div className="detail-ctas">
                    <button
                        id="detail-apply-btn"
                        className="btn btn-primary btn-lg detail-cta-btn"
                        onClick={() => setShowApplyModal(true)}
                    >
                        <Zap size={16} /> {tr(UI.applyNow)}
                    </button>
                    <button className="btn btn-ghost btn-lg" onClick={() => navigate('/csc-finder')}>
                        <MapPin size={16} /> {tr(UI.offlineHelp)}
                    </button>
                </div>

                {showApplyModal && (
                    <ApplyMethodModal scheme={scheme} onClose={() => setShowApplyModal(false)} />
                )}

            </main>
            <BottomNav />
        </div>
    )
}
