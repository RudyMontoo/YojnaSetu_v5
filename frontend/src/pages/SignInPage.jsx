import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Smartphone, KeyRound, ChevronLeft, Mail } from 'lucide-react'
import { gateway } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import './SignInPage.css'

const UI = {
    tagline: 'Login with your mobile number or email. An OTP will be sent to you.',
    mobile: 'Mobile Number', email: 'Email Address', sendOtp: 'Send OTP',
    useEmail: 'Use email instead', useMobile: 'Use mobile instead',
    privacy: 'No password needed. Your details stay private and encrypted.',
    otpSentTo: 'Enter the 6-digit OTP sent to', verifyLogin: 'Verify & Login',
    changeContact: 'Change',
    errSend: 'Could not send OTP. Try again.', errOtp: 'Incorrect OTP',
}

// v5.0 auth: phone OR email → OTP → httpOnly cookies from the Spring Boot gateway.
// No password, no Supabase — matches how the backend actually works. Email is the
// working channel today (SMS needs India DLT registration; wired for later).
export default function SignInPage() {
    const navigate = useNavigate()
    const [mode, setMode] = useState('mobile')  // mobile | email
    const [step, setStep] = useState('contact')  // contact | otp
    const [phone, setPhone] = useState('')
    const [email, setEmail] = useState('')
    const [otp, setOtp] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const tr = useAutoTranslate([...Object.values(UI), error].filter(Boolean))

    const digits = phone.replace(/\D/g, '')
    const fullPhone = phone.startsWith('+') ? phone : `+91${digits}`
    const isEmail = mode === 'email'
    const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())
    // what we show back to the user + send to the backend
    const contactLabel = isEmail ? email.trim() : fullPhone
    const identifier = isEmail ? { email: email.trim() } : { phone: fullPhone }
    const canSend = isEmail ? emailValid : digits.length >= 10

    const sendOtp = async (e) => {
        e.preventDefault()
        setError(''); setLoading(true)
        try {
            await gateway.sendOtp(identifier)
            setStep('otp')
        } catch (err) {
            setError(err.message || UI.errSend)
        } finally { setLoading(false) }
    }

    const verifyOtp = async (e) => {
        e.preventDefault()
        setError(''); setLoading(true)
        try {
            const res = await gateway.verifyOtp(identifier, otp.trim())
            try { await gateway.giveConsent() } catch { /* retried on first profile save */ }
            localStorage.setItem('yojna_user', JSON.stringify({
                id: res.user?.id,
                phone: res.user?.phone || (isEmail ? '' : fullPhone),
                email: res.user?.email || (isEmail ? email.trim() : ''),
                name: '',
                language: res.user?.language || 'en',
            }))
            navigate('/home')
        } catch (err) {
            setError(err.message || UI.errOtp)
            setLoading(false)
        }
    }

    const switchMode = () => {
        setMode(isEmail ? 'mobile' : 'email')
        setError('')
    }

    return (
        <div className="signin-wrapper">
            <div className="signin-bg-glow" />
            <div className="signin-card glass-card">

                <div className="signin-logo" style={{ justifyContent: 'center', marginBottom: 4 }}>
                    <div className="logo-img-circle" style={{ width: 72, height: 72 }}>
                        <img src="/logo.png" alt="Yojna Setu" className="logo-img" />
                    </div>
                </div>
                <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>
                    Yojna<span className="text-saffron">Setu</span>
                </h1>
                <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 18 }}>
                    {tr(UI.tagline)}
                </p>

                {error && <p className="signin-error">{tr(error)}</p>}

                {step === 'contact' ? (
                    <form onSubmit={sendOtp} className="signin-form">
                        <p className="signin-label">{tr(isEmail ? UI.email : UI.mobile)}</p>
                        <div className="signin-input-row">
                            {isEmail ? (
                                <>
                                    <span className="signin-prefix"><Mail size={15} /></span>
                                    <input
                                        type="email" inputMode="email" placeholder="you@example.com"
                                        value={email} onChange={e => setEmail(e.target.value)}
                                        className="input-glass signin-input" autoFocus required
                                    />
                                </>
                            ) : (
                                <>
                                    <span className="signin-prefix"><Smartphone size={15} /> +91</span>
                                    <input
                                        type="tel" inputMode="numeric" placeholder="98765 43210"
                                        value={phone} onChange={e => setPhone(e.target.value)}
                                        className="input-glass signin-input" autoFocus required
                                    />
                                </>
                            )}
                        </div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti"
                                disabled={loading || !canSend}>
                            {loading ? <span className="btn-spinner" /> : <><span>{tr(UI.sendOtp)}</span> <ArrowRight size={16} /></>}
                        </button>
                        <button type="button" className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: 8 }}
                                onClick={switchMode}>
                            {isEmail ? <><Smartphone size={14} /> {tr(UI.useMobile)}</> : <><Mail size={14} /> {tr(UI.useEmail)}</>}
                        </button>
                        <p className="text-subtle" style={{ fontSize: 12, textAlign: 'center', marginTop: 10 }}>
                            {tr(UI.privacy)}
                        </p>
                    </form>
                ) : (
                    <form onSubmit={verifyOtp} className="signin-form">
                        <p className="signin-label">{tr(UI.otpSentTo)} {contactLabel}</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><KeyRound size={15} /></span>
                            <input
                                inputMode="numeric" maxLength={6} placeholder="••••••"
                                value={otp} onChange={e => setOtp(e.target.value)}
                                className="input-glass signin-input"
                                style={{ letterSpacing: 8, fontWeight: 700, fontSize: 18 }}
                                autoFocus required
                            />
                        </div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti"
                                disabled={loading || otp.trim().length !== 6}>
                            {loading ? <span className="btn-spinner" /> : <><span>{tr(UI.verifyLogin)}</span> <ArrowRight size={16} /></>}
                        </button>
                        <button type="button" className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: 8 }}
                                onClick={() => { setStep('contact'); setOtp(''); setError('') }}>
                            <ChevronLeft size={14} /> {tr(UI.changeContact)}
                        </button>
                    </form>
                )}
            </div>
        </div>
    )
}
