import { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { ArrowLeft, CheckCircle, XCircle, ExternalLink, MapPin, FileText, Zap } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import ApplyMethodModal from '../components/ApplyMethodModal'
import '../components/components.css'
import './SchemeDetailPage.css'

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

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                {/* Breadcrumb */}
                <div className="detail-breadcrumb">
                    <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>
                        <ArrowLeft size={14} /> Back
                    </button>
                    <span className="text-subtle">Schemes / {scheme.shortName}</span>
                </div>

                {/* Hero */}
                <div className="glass-card detail-hero">
                    <div className="detail-hero-icon">{scheme.icon}</div>
                    <div className="detail-hero-info">
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                            <span className="badge badge-saffron">{scheme.category}</span>
                            <span className="badge badge-muted">{scheme.tag}</span>
                        </div>
                        <h1 className="detail-title">{scheme.name}</h1>
                        <p className="text-muted detail-ministry">{scheme.ministry}</p>
                    </div>
                </div>

                {/* Benefit highlight */}
                <div className="detail-benefit-card glass-card">
                    <span className="detail-benefit-label text-muted">Key Benefit:</span>
                    <p className="detail-benefit-text text-saffron">{scheme.benefit}</p>
                </div>

                {/* Tabs */}
                <div className="detail-tabs">
                    {TABS.map(tab => (
                        <button key={tab} className={`chip ${activeTab === tab ? 'active' : ''}`} onClick={() => setActiveTab(tab)}>
                            {tab}
                        </button>
                    ))}
                </div>

                {/* Tab Content */}
                <div className="glass-card detail-tab-content">

                    {activeTab === 'Overview' && (
                        <p className="detail-overview-text">{scheme.overview}</p>
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
                                    <span className="detail-elig-text">{item.text}</span>
                                </div>
                            ))}
                            <p className="text-muted detail-elig-note">
                                ✅ = You likely qualify &nbsp;|&nbsp; ? = Verify on official portal
                            </p>
                        </div>
                    )}

                    {activeTab === 'Documents' && (
                        <ol className="detail-docs-list">
                            {scheme.documents.map((doc, i) => (
                                <li key={i} className="detail-doc-item">
                                    <div className="detail-doc-num">{i + 1}</div>
                                    <FileText size={16} className="text-saffron" />
                                    <span>{doc}</span>
                                </li>
                            ))}
                        </ol>
                    )}

                    {activeTab === 'How to Apply' && (
                        <div className="detail-apply-steps">
                            {[
                                'Visit Jan Seva Kendra (CSC) or the official portal',
                                'Fill out the application form and provide required documents',
                                'Submit the form — you will receive an Application ID',
                                'Track status under "My Applications"',
                            ].map((step, i) => (
                                <div key={i} className="detail-apply-step">
                                    <div className="detail-step-num">{i + 1}</div>
                                    <p>{step}</p>
                                </div>
                            ))}
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
                        <Zap size={16} /> Apply Now
                    </button>
                    <button className="btn btn-ghost btn-lg" onClick={() => navigate(`/helpers?scheme=${encodeURIComponent(scheme.name)}`)}>
                        <MapPin size={16} /> Get Offline Help
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
