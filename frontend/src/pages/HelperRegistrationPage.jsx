import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CheckCircle, Loader2, UserPlus, ShieldCheck, Upload, FileText, X } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './HelperRegistrationPage.css'

const INDIAN_LANGUAGES = [
    'Hindi', 'English', 'Marathi', 'Bengali', 'Tamil', 'Telugu',
    'Kannada', 'Gujarati', 'Punjabi', 'Odia', 'Malayalam', 'Assamese'
]

const SERVICES = [
    'PM-Kisan', 'PMAY (Housing)', 'Ayushman Bharat', 'E-Shram',
    'Ration Card', 'Aadhaar', 'PAN Card', 'Scholarship',
    'Old Age Pension', 'Widow Pension', 'Birth Certificate',
    'Caste Certificate', 'Land Records', 'Driving Licence'
]

const STATES = [
    'Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh',
    'Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka',
    'Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram',
    'Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana',
    'Tripura','Uttar Pradesh','Uttarakhand','West Bengal','Delhi','Jammu & Kashmir'
]

const DOC_TYPES = [
    { value: 'aadhaar',         label: '🪪 Aadhaar Card' },
    { value: 'pan',             label: '💳 PAN Card' },
    { value: 'voter_id',        label: '🗳️ Voter ID' },
    { value: 'driving_licence', label: '🚗 Driving Licence' },
    { value: 'passport',        label: '📕 Passport' },
]

const STEPS = ['Personal Info', 'Location', 'Skills', 'ID Verification']

export default function HelperRegistrationPage() {
    const navigate = useNavigate()
    const fileRef = useRef(null)
    const [step, setStep] = useState(1)
    const [loading, setLoading] = useState(false)
    const [done, setDone] = useState(null)   // null | { message }
    const [error, setError] = useState('')

    const [form, setForm] = useState({
        name: '', email: '', phone: '',
        state: '', district: '', bio: '',
        languages: [], services: [],
    })

    // Step 4 — document
    const [docType, setDocType] = useState('')
    const [docFile, setDocFile] = useState(null)  // File object
    const [docPreview, setDocPreview] = useState(null)  // object URL for images

    const update = (k, v) => setForm(f => ({ ...f, [k]: v }))

    const toggleItem = (key, val) => {
        setForm(f => {
            const arr = f[key]
            return { ...f, [key]: arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val] }
        })
    }

    const handleFileSelect = (e) => {
        const file = e.target.files[0]
        if (!file) return
        if (file.size > 5 * 1024 * 1024) {
            setError('File too large. Please upload a file smaller than 5MB.')
            return
        }
        setDocFile(file)
        setError('')
        if (file.type.startsWith('image/')) {
            setDocPreview(URL.createObjectURL(file))
        } else {
            setDocPreview(null)  // PDF — no preview
        }
    }

    const removeFile = () => {
        setDocFile(null)
        setDocPreview(null)
        if (fileRef.current) fileRef.current.value = ''
    }

    const canNext = () => {
        if (step === 1) return form.name.trim() && form.email.trim() && form.phone.trim()
        if (step === 2) return form.state && form.district.trim()
        if (step === 3) return form.languages.length > 0 && form.services.length > 0
        if (step === 4) return docType && docFile
        return false
    }

    const submit = async () => {
        if (!docType || !docFile) {
            setError('Please select a document type and upload your ID.')
            return
        }
        setLoading(true)
        setError('')
        try {
            // Use FormData for multipart upload (file + fields)
            const fd = new FormData()
            fd.append('name',      form.name.trim())
            fd.append('email',     form.email.trim())
            fd.append('phone',     form.phone.trim())
            fd.append('district',  form.district.trim())
            fd.append('state',     form.state)
            fd.append('languages', form.languages.join(','))
            fd.append('services',  form.services.join(','))
            fd.append('bio',       form.bio.trim())
            fd.append('doc_type',  docType)
            fd.append('document',  docFile)

            const res = await fetch('/sahayak/register', {
                method: 'POST',
                body: fd,  // No Content-Type header — browser sets multipart boundary
            })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || 'Registration failed')
            setDone(data)
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    // ── Success screen ──────────────────────────────────────────
    if (done) {
        return (
            <div className="page-wrapper">
                <Navbar />
                <main className="page-content helper-reg-main">
                    <div className="helper-reg-success glass-card">
                        <div className="helper-reg-success-icon">
                            <ShieldCheck size={48} />
                        </div>
                        <h2>Registration Submitted! 🙏</h2>
                        <p>{done.message}</p>
                        <div className="helper-reg-pending-notice">
                            <p>📋 <strong>What happens next?</strong></p>
                            <ul>
                                <li>Our team will verify your submitted document</li>
                                <li>You'll receive a confirmation email within 24 hours</li>
                                <li>Once verified, citizens in <strong>{form.district}, {form.state}</strong> can book you</li>
                            </ul>
                        </div>
                        <div className="helper-reg-success-btns">
                            <button className="btn btn-ghost" onClick={() => navigate('/home')}>
                                Back to Home
                            </button>
                        </div>
                    </div>
                </main>
                <BottomNav />
            </div>
        )
    }

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content helper-reg-main">

                {/* Header */}
                <div className="helper-reg-header">
                    <button className="btn btn-ghost btn-sm" onClick={() => step > 1 ? setStep(s => s - 1) : navigate(-1)}>
                        <ArrowLeft size={16} /> Back
                    </button>
                    <div className="helper-reg-title-wrap">
                        <UserPlus size={20} className="text-saffron" />
                        <h1 className="helper-reg-title">Become a Jan Sahayak</h1>
                    </div>
                    <p className="text-muted helper-reg-sub">
                        Help people in your community apply for government schemes.
                    </p>
                </div>

                {/* Progress — 4 steps now */}
                <div className="helper-reg-progress">
                    {STEPS.map((label, i) => {
                        const s = i + 1
                        return (
                            <div key={s} className={`helper-reg-step ${s <= step ? 'active' : ''} ${s < step ? 'done' : ''}`}>
                                <div className="helper-reg-step-dot">
                                    {s < step ? <CheckCircle size={14} /> : s}
                                </div>
                                <span className="helper-reg-step-label">{label}</span>
                            </div>
                        )
                    })}
                </div>

                {/* Steps */}
                <div className="glass-card helper-reg-card">

                    {step === 1 && (
                        <div className="helper-reg-fields">
                            <h3 className="helper-reg-step-title">Tell us about yourself</h3>
                            <div className="field-group">
                                <label className="field-label">Full Name *</label>
                                <input className="input-glass" placeholder="e.g. Ramesh Sharma"
                                    value={form.name} onChange={e => update('name', e.target.value)} />
                            </div>
                            <div className="field-group">
                                <label className="field-label">Email Address *</label>
                                <input className="input-glass" placeholder="your@email.com" type="email"
                                    value={form.email} onChange={e => update('email', e.target.value)} />
                                <p className="field-hint">Appointment requests will be sent to this email.</p>
                            </div>
                            <div className="field-group">
                                <label className="field-label">Phone Number *</label>
                                <input className="input-glass" placeholder="+91-XXXXX-XXXXX" type="tel"
                                    value={form.phone} onChange={e => update('phone', e.target.value)} />
                            </div>
                            <div className="field-group">
                                <label className="field-label">Short Bio (optional)</label>
                                <textarea className="input-glass helper-reg-bio"
                                    placeholder="e.g. I am a retired government employee with 20 years experience..."
                                    value={form.bio} onChange={e => update('bio', e.target.value)} rows={3} />
                            </div>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="helper-reg-fields">
                            <h3 className="helper-reg-step-title">Where are you located?</h3>
                            <div className="field-group">
                                <label className="field-label">State *</label>
                                <select className="input-glass" value={form.state} onChange={e => update('state', e.target.value)}>
                                    <option value="">Select state</option>
                                    {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                                </select>
                            </div>
                            <div className="field-group">
                                <label className="field-label">District *</label>
                                <input className="input-glass" placeholder="e.g. Pune"
                                    value={form.district} onChange={e => update('district', e.target.value)} />
                            </div>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="helper-reg-fields">
                            <h3 className="helper-reg-step-title">Your Skills & Services</h3>
                            <div className="field-group">
                                <label className="field-label">Languages you can assist in *</label>
                                <div className="helper-reg-chips">
                                    {INDIAN_LANGUAGES.map(l => (
                                        <button key={l} className={`chip ${form.languages.includes(l) ? 'active' : ''}`}
                                            onClick={() => toggleItem('languages', l)} type="button">{l}</button>
                                    ))}
                                </div>
                            </div>
                            <div className="field-group" style={{ marginTop: 8 }}>
                                <label className="field-label">Services you can help with *</label>
                                <div className="helper-reg-chips">
                                    {SERVICES.map(s => (
                                        <button key={s} className={`chip ${form.services.includes(s) ? 'active' : ''}`}
                                            onClick={() => toggleItem('services', s)} type="button">{s}</button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {step === 4 && (
                        <div className="helper-reg-fields">
                            <h3 className="helper-reg-step-title">Identity Verification</h3>

                            <div className="helper-reg-notice">
                                <ShieldCheck size={16} className="text-saffron" />
                                <p>To prevent fraud and protect citizens, we require one valid government-issued ID. Your document is stored securely and never shared publicly.</p>
                            </div>

                            <div className="field-group">
                                <label className="field-label">Document Type *</label>
                                <div className="helper-doc-type-grid">
                                    {DOC_TYPES.map(d => (
                                        <button
                                            key={d.value}
                                            type="button"
                                            className={`helper-doc-type-btn ${docType === d.value ? 'selected' : ''}`}
                                            onClick={() => setDocType(d.value)}
                                        >
                                            {d.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="field-group">
                                <label className="field-label">Upload Document * <span className="field-hint-inline">(JPG, PNG, PDF — max 5MB)</span></label>
                                {docFile ? (
                                    <div className="helper-doc-preview">
                                        {docPreview ? (
                                            <img src={docPreview} alt="Document preview" className="helper-doc-img" />
                                        ) : (
                                            <div className="helper-doc-pdf-icon">
                                                <FileText size={32} className="text-saffron" />
                                                <span>{docFile.name}</span>
                                            </div>
                                        )}
                                        <button type="button" className="helper-doc-remove" onClick={removeFile}>
                                            <X size={16} /> Remove
                                        </button>
                                    </div>
                                ) : (
                                    <div className="helper-doc-upload-zone" onClick={() => fileRef.current?.click()}>
                                        <Upload size={28} className="text-muted" />
                                        <p className="text-muted" style={{ margin: '8px 0 4px', fontSize: 14 }}>
                                            Click to upload your document
                                        </p>
                                        <p className="text-subtle" style={{ fontSize: 12 }}>
                                            Clear photo of the front of your ID card
                                        </p>
                                    </div>
                                )}
                                <input ref={fileRef} type="file" accept="image/*,.pdf" hidden onChange={handleFileSelect} />
                            </div>

                            {error && <p className="helper-reg-error">{error}</p>}
                        </div>
                    )}

                    {/* Navigation */}
                    <div className="helper-reg-nav">
                        {step < 4 ? (
                            <button className="btn btn-primary helper-reg-next" disabled={!canNext()} onClick={() => setStep(s => s + 1)}>
                                Continue <ArrowRight size={16} />
                            </button>
                        ) : (
                            <button className="btn btn-primary helper-reg-next" disabled={!canNext() || loading} onClick={submit}>
                                {loading ? <Loader2 size={16} className="spin" /> : <ShieldCheck size={16} />}
                                {loading ? 'Submitting...' : 'Submit for Verification'}
                            </button>
                        )}
                    </div>
                </div>

                <div style={{ height: 80 }} />
            </main>
            <BottomNav />
        </div>
    )
}
