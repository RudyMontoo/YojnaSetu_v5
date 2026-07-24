import { useState, useEffect } from 'react'
import { ShieldCheck, Send, CheckCircle, Clock, XCircle, IdCard } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { Reveal } from '../components/motion'
import { gateway } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'

const UI = {
    tag: 'Helper Programme', title: 'Become a Yojna Setu Helper',
    intro: 'Help citizens near you apply for schemes. Submit your KYC — an admin will verify and approve you.',
    privacy: 'Your Aadhaar is hashed (never stored raw) and no document image is kept.',
    fullName: 'Full name (as on Aadhaar)', phone: 'Phone number',
    aadhaar: 'Aadhaar number (12 digits)', pan: 'PAN (ABCDE1234F)',
    workType: 'Proof of work', workDetail: 'Organisation / role details',
    submit: 'Submit Application',
    errGeneric: 'Could not submit. Please try again.',
    pendingT: 'Application under review', pendingS: 'An admin will verify your KYC and approve you soon.',
    approvedT: 'You are an approved Helper! 🎉', approvedS: 'Log out and back in to unlock the Helper Dashboard.',
    rejectedT: 'Application not approved', rejectedS: 'You can review your details and apply again.',
    aadhaarBad: 'Aadhaar checksum failed — please re-check the number.',
}

const WORK_TYPES = [
    { value: 'csc_operator', label: 'CSC / Jan Seva Kendra operator' },
    { value: 'ngo', label: 'NGO / social worker' },
    { value: 'panchayat', label: 'Panchayat / Gram Sabha member' },
    { value: 'bank_mitra', label: 'Bank Mitra / BC agent' },
    { value: 'other', label: 'Other' },
]

export default function BecomeHelperPage() {
    const savedUser = (() => { try { return JSON.parse(localStorage.getItem('yojna_user') || '{}') } catch { return {} } })()
    const [fullName, setFullName] = useState('')
    const [phone, setPhone] = useState(savedUser.phone || '')
    const [aadhaar, setAadhaar] = useState('')
    const [pan, setPan] = useState('')
    const [workType, setWorkType] = useState(WORK_TYPES[0].value)
    const [workDetail, setWorkDetail] = useState('')
    const [status, setStatus] = useState(null)     // null | none | pending | approved | rejected
    const [loading, setLoading] = useState(true)
    const [sending, setSending] = useState(false)
    const [error, setError] = useState('')

    const tr = useAutoTranslate([...Object.values(UI), ...WORK_TYPES.map(w => w.label), error].filter(Boolean))

    useEffect(() => {
        gateway.myHelperApplication()
            .then(r => setStatus(r.status || 'none'))
            .catch(() => setStatus('none'))
            .finally(() => setLoading(false))
    }, [])

    const submit = async (e) => {
        e.preventDefault()
        setError(''); setSending(true)
        try {
            const res = await gateway.applyHelper({ fullName: fullName.trim(), phone: phone.trim(), aadhaar: aadhaar.replace(/\s/g, ''), pan: pan.trim().toUpperCase(), workProofType: workType, workProofDetail: workDetail.trim() })
            if (res.aadhaarVerified === false) { /* still submitted, admin will see the flag */ }
            setStatus('pending')
        } catch (err) {
            setError(err.message || UI.errGeneric)
        } finally { setSending(false) }
    }

    const StatusCard = ({ Icon, title, sub, cls }) => (
        <Reveal><div className={`glass-card ${cls}`} style={{ padding: 22, textAlign: 'center' }}>
            <Icon size={40} className="text-saffron" />
            <h2 style={{ marginTop: 10, marginBottom: 4 }}>{tr(title)}</h2>
            <p className="text-muted" style={{ fontSize: 14 }}>{tr(sub)}</p>
        </div></Reveal>
    )

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">
                <div className="status-header">
                    <div>
                        <div className="sathi-tag" style={{ position: 'static', display: 'inline-flex', marginBottom: 8 }}>
                            <ShieldCheck size={10} /> {tr(UI.tag)}
                        </div>
                        <h1 className="status-title font-display">{tr(UI.title)}</h1>
                        <p className="text-muted" style={{ fontSize: 13, marginTop: 4 }}>{tr(UI.intro)}</p>
                    </div>
                </div>

                {loading ? (
                    <div className="glass-card" style={{ padding: 22, textAlign: 'center' }}><span className="btn-spinner" /></div>
                ) : status === 'pending' ? (
                    <StatusCard Icon={Clock} title={UI.pendingT} sub={UI.pendingS} cls="" />
                ) : status === 'approved' ? (
                    <StatusCard Icon={CheckCircle} title={UI.approvedT} sub={UI.approvedS} cls="glass-card-glow" />
                ) : (
                    <>
                        {status === 'rejected' && <StatusCard Icon={XCircle} title={UI.rejectedT} sub={UI.rejectedS} cls="" />}
                        <Reveal><form onSubmit={submit} className="glass-card" style={{ padding: 18, marginTop: status === 'rejected' ? 14 : 0 }}>
                            {error && <p className="signin-error" style={{ marginBottom: 10 }}>{tr(error)}</p>}
                            <p className="csc-label">{tr(UI.fullName)}</p>
                            <input className="input-glass" value={fullName} onChange={e => setFullName(e.target.value)} style={{ width: '100%', marginBottom: 10 }} required />
                            <p className="csc-label">{tr(UI.phone)}</p>
                            <input className="input-glass" inputMode="tel" value={phone} onChange={e => setPhone(e.target.value)} style={{ width: '100%', marginBottom: 10 }} required />
                            <p className="csc-label">{tr(UI.aadhaar)}</p>
                            <input className="input-glass" inputMode="numeric" maxLength={14} value={aadhaar} onChange={e => setAadhaar(e.target.value)} placeholder="1234 5678 9012" style={{ width: '100%', marginBottom: 10 }} required />
                            <p className="csc-label">{tr(UI.pan)}</p>
                            <input className="input-glass" value={pan} onChange={e => setPan(e.target.value.toUpperCase())} placeholder="ABCDE1234F" maxLength={10} style={{ width: '100%', marginBottom: 10 }} required />
                            <p className="csc-label">{tr(UI.workType)}</p>
                            <select className="input-glass" value={workType} onChange={e => setWorkType(e.target.value)} style={{ width: '100%', marginBottom: 10 }}>
                                {WORK_TYPES.map(w => <option key={w.value} value={w.value}>{tr(w.label)}</option>)}
                            </select>
                            <p className="csc-label">{tr(UI.workDetail)}</p>
                            <input className="input-glass" value={workDetail} onChange={e => setWorkDetail(e.target.value)} placeholder="e.g. CSC ID 123, Peth Naka" style={{ width: '100%', marginBottom: 12 }} />
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
                                <IdCard size={14} className="text-muted" />
                                <span className="text-muted" style={{ fontSize: 12 }}>{tr(UI.privacy)}</span>
                            </div>
                            <button type="submit" className="btn btn-primary btn-aarti" style={{ width: '100%' }} disabled={sending}>
                                {sending ? <span className="btn-spinner" /> : <><Send size={15} /> {tr(UI.submit)}</>}
                            </button>
                        </form></Reveal>
                    </>
                )}
            </main>
            <BottomNav />
        </div>
    )
}
