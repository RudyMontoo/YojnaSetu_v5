import { useState } from 'react'
import { Search, ShieldAlert, CheckCircle2, XCircle, Loader2, Building2 } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { Reveal } from '../components/motion'
import { Sparkles } from 'lucide-react'
import { ai } from '../lib/api'
import '../components/components.css'
import './CscDashboardPage.css'

// Agent 9 — CSC Assist. Real operator tool: a citizen at the counter is
// missing one document for a scheme; this asks what's an accepted
// substitute in actual Indian government practice (not a guess — the
// backend grounds the LLM in the scheme's real document list and is
// explicitly told to say "no substitute" rather than invent one).
const DOC_TYPES = [
    { value: 'aadhaar', label: 'Aadhaar Card' },
    { value: 'pan', label: 'PAN Card' },
    { value: 'voter_id', label: 'Voter ID Card' },
    { value: 'ration_card', label: 'Ration Card' },
    { value: 'income_cert', label: 'Income Certificate' },
    { value: 'caste_cert', label: 'Caste Certificate' },
    { value: 'driving_licence', label: 'Driving Licence' },
    { value: 'passport', label: 'Passport' },
    { value: 'disability_cert', label: 'Disability Certificate' },
    { value: 'land_record', label: 'Land Record / Khasra' },
    { value: 'service_cert', label: 'Service Certificate' },
    { value: 'bank_passbook', label: 'Bank Passbook' },
]

export default function CscDashboardPage() {
    const [schemeCode, setSchemeCode] = useState('')
    const [docType, setDocType] = useState(DOC_TYPES[0].value)
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState('')

    const submit = async (e) => {
        e.preventDefault()
        if (!schemeCode.trim()) return
        setLoading(true); setError(''); setResult(null)
        try {
            const res = await ai.cscAlternatives(schemeCode.trim(), docType)
            setResult(res)
        } catch (err) {
            if (err.status === 403) {
                setError('This tool is for CSC operators only. Your account isn\'t marked as an operator.')
            } else if (err.status === 404) {
                setError(`No scheme found for code "${schemeCode.trim()}" — check the code and try again.`)
            } else if (err.status === 401) {
                setError('Please login again — your session has expired.')
            } else {
                setError(err.message || 'Could not reach the alternatives service.')
            }
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">
                <div className="status-header">
                    <div>
                        <div className="sathi-tag" style={{ position: 'static', display: 'inline-flex', marginBottom: 8 }}>
                            <Building2 size={10} /> Agent 9 · CSC Operator Assist
                        </div>
                        <h1 className="status-title font-display">Missing Document Helper</h1>
                        <p className="text-muted" style={{ fontSize: 13, marginTop: 4 }}>
                            Citizen at your counter is missing a document? Check for a real, accepted alternative before turning them away.
                        </p>
                    </div>
                </div>

                <Reveal><form onSubmit={submit} className="glass-card csc-form">
                    <label className="csc-field">
                        <span className="csc-label">Scheme code</span>
                        <input
                            className="input-glass"
                            placeholder="e.g. central-agriculture-pm-fasal-bima-yojana"
                            value={schemeCode}
                            onChange={e => setSchemeCode(e.target.value)}
                            required
                        />
                    </label>

                    <label className="csc-field">
                        <span className="csc-label">Missing document</span>
                        <select className="input-glass" value={docType} onChange={e => setDocType(e.target.value)}>
                            {DOC_TYPES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
                        </select>
                    </label>

                    <button className="btn btn-primary btn-aarti" disabled={loading || !schemeCode.trim()}>
                        {loading ? <Loader2 size={15} className="spin" /> : <Search size={15} />}
                        {loading ? 'Checking…' : 'Find Alternatives'}
                    </button>
                </form></Reveal>

                {error && (
                    <div className="glass-card" style={{ padding: 14, marginTop: 16, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                        <ShieldAlert size={18} className="text-saffron" style={{ flexShrink: 0, marginTop: 1 }} />
                        <p style={{ fontSize: 13.5 }}>{error}</p>
                    </div>
                )}

                {result && (
                    <Reveal><div className="glass-card glass-card-glow" style={{ padding: 18, marginTop: 16 }}>
                        <h2 className="status-scheme-name" style={{ marginBottom: 4 }}>{result.scheme_name}</h2>
                        <p className="text-muted" style={{ fontSize: 12, marginBottom: 14 }}>
                            Missing: {DOC_TYPES.find(d => d.value === docType)?.label || docType}
                        </p>

                        {result.mandatory_no_substitute ? (
                            <div className="csc-verdict csc-verdict-block">
                                <XCircle size={16} /> Mandatory — no substitute accepted
                            </div>
                        ) : result.has_alternatives ? (
                            <div className="csc-verdict csc-verdict-ok">
                                <CheckCircle2 size={16} /> Alternatives available
                            </div>
                        ) : (
                            <div className="csc-verdict csc-verdict-block">
                                <XCircle size={16} /> No realistic alternative found
                            </div>
                        )}

                        {result.alternatives?.length > 0 && (
                            <div className="csc-alt-list">
                                {result.alternatives.map((alt, i) => (
                                    <div key={i} className="csc-alt-item">
                                        <p className="csc-alt-name"><Sparkles size={12} className="text-saffron" /> {alt.document}</p>
                                        <p className="csc-alt-how">{alt.how_to_get}</p>
                                        {alt.note && <p className="csc-alt-note">{alt.note}</p>}
                                    </div>
                                ))}
                            </div>
                        )}

                        {result.operator_advice && (
                            <div className="csc-advice">
                                <p className="csc-label">Advice for you</p>
                                <p style={{ fontSize: 13.5 }}>{result.operator_advice}</p>
                            </div>
                        )}
                    </div></Reveal>
                )}
            </main>
            <BottomNav />
        </div>
    )
}
