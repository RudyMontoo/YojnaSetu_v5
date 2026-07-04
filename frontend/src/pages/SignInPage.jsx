import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Smartphone, KeyRound, ChevronLeft } from 'lucide-react'
import { gateway } from '../lib/api'
import './SignInPage.css'

// v5.0 auth: phone → OTP → httpOnly cookies from the Spring Boot gateway.
// No email, no password, no Supabase — matches how the backend actually works.
export default function SignInPage() {
    const navigate = useNavigate()
    const [step, setStep] = useState('phone')   // phone | otp
    const [phone, setPhone] = useState('')
    const [otp, setOtp] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const digits = phone.replace(/\D/g, '')
    const fullPhone = phone.startsWith('+') ? phone : `+91${digits}`

    const sendOtp = async (e) => {
        e.preventDefault()
        setError(''); setLoading(true)
        try {
            await gateway.sendOtp(fullPhone)
            setStep('otp')
        } catch (err) {
            setError(err.message || 'Could not send OTP. Try again.')
        } finally { setLoading(false) }
    }

    const verifyOtp = async (e) => {
        e.preventDefault()
        setError(''); setLoading(true)
        try {
            const res = await gateway.verifyOtp(fullPhone, otp.trim())
            try { await gateway.giveConsent() } catch { /* retried on first profile save */ }
            localStorage.setItem('yojna_user', JSON.stringify({
                id: res.user?.id,
                phone: res.user?.phone || fullPhone,
                name: '',
                language: res.user?.language || 'en',
            }))
            navigate('/home')
        } catch (err) {
            setError(err.message || 'Incorrect OTP')
            setLoading(false)
        }
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
                    Login with your mobile number. An OTP will be sent by SMS.
                </p>

                {error && <p className="signin-error">{error}</p>}

                {step === 'phone' ? (
                    <form onSubmit={sendOtp} className="signin-form">
                        <p className="signin-label">Mobile Number</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><Smartphone size={15} /> +91</span>
                            <input
                                type="tel" inputMode="numeric" placeholder="98765 43210"
                                value={phone} onChange={e => setPhone(e.target.value)}
                                className="input-glass signin-input" autoFocus required
                            />
                        </div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn btn-aarti"
                                disabled={loading || digits.length < 10}>
                            {loading ? <span className="btn-spinner" /> : <><span>Send OTP</span> <ArrowRight size={16} /></>}
                        </button>
                        <p className="text-subtle" style={{ fontSize: 12, textAlign: 'center', marginTop: 10 }}>
                            No password needed. Your number stays private and encrypted.
                        </p>
                    </form>
                ) : (
                    <form onSubmit={verifyOtp} className="signin-form">
                        <p className="signin-label">Enter the 6-digit OTP sent to {fullPhone}</p>
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
                            {loading ? <span className="btn-spinner" /> : <><span>Verify &amp; Login</span> <ArrowRight size={16} /></>}
                        </button>
                        <button type="button" className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: 8 }}
                                onClick={() => { setStep('phone'); setOtp(''); setError('') }}>
                            <ChevronLeft size={14} /> Change number
                        </button>
                    </form>
                )}
            </div>
        </div>
    )
}
