import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Smartphone, KeyRound, ChevronLeft, Mail } from 'lucide-react'
import { RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth'
import { gateway } from '../lib/api'
import { auth } from '../lib/firebase'
import { useAutoTranslate } from '../lib/i18n'
import Disclaimer from '../components/Disclaimer'
import './SignInPage.css'

const UI = {
    tagline: 'Login with your mobile number or email. An OTP will be sent to you.',
    mobile: 'Mobile Number', email: 'Email Address', sendOtp: 'Send OTP',
    useEmail: 'Use email instead', useMobile: 'Use mobile instead',
    privacy: 'No password needed. Your details stay private and encrypted.',
    otpSentTo: 'Enter the 6-digit OTP sent to', verifyLogin: 'Verify & Login',
    changeContact: 'Change',
    errSend: 'Could not send OTP. Try again.', errOtp: 'Incorrect OTP',
    errVerify: 'Could not complete login. Please try again.',
    errPhone: 'Please enter a valid mobile number.',
    errTooMany: 'Too many attempts — please wait a while and try again.',
    errExpired: 'That OTP has expired. Tap Change and request a new one.',
    errDomain: 'Login is not enabled for this web address. Please contact support.',
    errRecaptcha: 'Verification check failed. Reload the page and try again.',
}

// v5.0 auth: EMAIL OTP goes through our Spring gateway (Brevo). MOBILE OTP goes
// through Firebase Phone Auth — Google sends the SMS (no DLT / SIM / WhatsApp
// Business needed); the browser gets a Firebase token, our backend verifies it
// (/auth/phone/verify) and issues the SAME httpOnly cookie session. No password.
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

    const confirmationRef = useRef(null)  // Firebase confirmationResult (mobile)
    const recaptchaRef = useRef(null)     // invisible reCAPTCHA verifier

    const digits = phone.replace(/\D/g, '')
    const fullPhone = phone.startsWith('+') ? phone : `+91${digits}`
    const isEmail = mode === 'email'
    const emailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())
    const contactLabel = isEmail ? email.trim() : fullPhone
    const canSend = isEmail ? emailValid : digits.length >= 10

    // ── shared post-login: store user + go home ──
    const finishLogin = (user) => {
        localStorage.setItem('yojna_user', JSON.stringify({
            id: user?.id,
            phone: user?.phone || (isEmail ? '' : fullPhone),
            email: user?.email || (isEmail ? email.trim() : ''),
            role: user?.role || 'CITIZEN',
            name: '',
            language: user?.language || 'en',
        }))
        navigate('/home')
    }

    // `fallback` matters: a Firebase code we don't recognise during VERIFY must not
    // claim "could not send OTP" — the SMS already went out by then. A gateway
    // error (from verifyPhone) carries .status, never .code, so it lands here too;
    // surfacing its real message is what makes a backend failure diagnosable
    // instead of masquerading as a send failure (2026-08-05 CORS 403).
    const mapFirebaseError = (err, fallback = UI.errSend) => {
        const code = err?.code
        if (code === 'auth/invalid-phone-number') return UI.errPhone
        if (code === 'auth/too-many-requests') return UI.errTooMany
        if (code === 'auth/invalid-verification-code') return UI.errOtp
        if (code === 'auth/code-expired') return UI.errExpired
        if (code === 'auth/unauthorized-domain') return UI.errDomain
        if (code && code.includes('recaptcha')) return UI.errRecaptcha
        if (!code && err?.message) return err.message   // gateway error — show what it said
        return fallback
    }

    const sendOtp = async (e) => {
        e.preventDefault()
        setError(''); setLoading(true)
        try {
            if (isEmail) {
                await gateway.sendOtp({ email: email.trim() })
            } else {
                // Firebase: one invisible reCAPTCHA per page, reused across retries.
                if (!recaptchaRef.current) {
                    // badge:'inline' renders the reCAPTCHA badge inside our own
                    // container (which we center) instead of Google's fixed
                    // bottom-right float.
                    recaptchaRef.current = new RecaptchaVerifier(auth, 'recaptcha-container', { size: 'invisible', badge: 'inline' })
                }
                confirmationRef.current = await signInWithPhoneNumber(auth, fullPhone, recaptchaRef.current)
            }
            setStep('otp')
        } catch (err) {
            setError(isEmail ? (err.message || UI.errSend) : mapFirebaseError(err, UI.errSend))
            // a failed reCAPTCHA can't be reused — drop it so the next try makes a fresh one
            try { recaptchaRef.current?.clear() } catch { /* noop */ }
            recaptchaRef.current = null
        } finally { setLoading(false) }
    }

    const verifyOtp = async (e) => {
        e.preventDefault()
        setError(''); setLoading(true)
        try {
            let res
            if (isEmail) {
                res = await gateway.verifyOtp({ email: email.trim() }, otp.trim())
            } else {
                const cred = await confirmationRef.current.confirm(otp.trim())
                const idToken = await cred.user.getIdToken()
                res = await gateway.verifyPhone(idToken)   // backend verifies + issues our cookie
            }
            try { await gateway.giveConsent() } catch { /* retried on first profile save */ }
            finishLogin(res.user)
        } catch (err) {
            setError(isEmail ? (err.message || UI.errOtp) : mapFirebaseError(err, UI.errVerify))
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
                        <img src="/logo.png" alt="Yojna Sarthi" className="logo-img" />
                    </div>
                </div>
                <h1 className="signin-brand font-display" style={{ textAlign: 'center', marginTop: 0 }}>
                    Yojna<span className="text-saffron">Sarthi</span>
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
                {/* Firebase reCAPTCHA badge renders here (inline mode), centered. */}
                <div id="recaptcha-container" style={{ display: 'flex', justifyContent: 'center', marginTop: 14 }} />
                <Disclaimer variant="site" style={{ marginTop: 16 }} />
            </div>
        </div>
    )
}
