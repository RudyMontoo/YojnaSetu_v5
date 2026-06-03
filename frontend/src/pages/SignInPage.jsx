import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, User, Mail, Lock, Calendar, UserPlus, ChevronRight } from 'lucide-react'
import { supabase } from '../lib/supabase'
import './SignInPage.css'

export default function SignInPage() {
    const navigate = useNavigate()
    const [mode, setMode] = useState('signin')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    // Sign in
    const [siEmail, setSiEmail] = useState('')
    const [siPassword, setSiPassword] = useState('')

    // Register
    const [regName, setRegName] = useState('')
    const [regDob, setRegDob] = useState('')
    const [regEmail, setRegEmail] = useState('')
    const [regPassword, setRegPassword] = useState('')

    const switchMode = (m) => { setMode(m); setError('') }

    /* ── Sign In ── */
    const handleSignIn = async (e) => {
        e.preventDefault()
        setError('')
        setLoading(true)
        try {
            const { data, error: err } = await supabase.auth.signInWithPassword({
                email: siEmail,
                password: siPassword,
            })
            if (err) throw err

            // Store user info locally for quick access
            const user = data.user
            const meta = user.user_metadata || {}
            localStorage.setItem('yojna_user', JSON.stringify({
                id: user.id,
                email: user.email,
                name: meta.name || meta.full_name || '',
                state: meta.state || '',
                language: meta.language || 'hi-IN',
            }))
            navigate('/home')
        } catch (err) {
            setError(err.message || 'Invalid email or password')
        } finally {
            setLoading(false)
        }
    }

    /* ── Register ── */
    const handleRegister = async (e) => {
        e.preventDefault()
        if (!regName.trim() || !regDob || !regEmail.includes('@') || regPassword.length < 6) {
            setError('Please fill all fields. Password must be at least 6 characters.')
            return
        }
        setError('')
        setLoading(true)
        const age = Math.floor((Date.now() - new Date(regDob)) / (365.25 * 24 * 3600 * 1000))

        try {
            const { data, error: err } = await supabase.auth.signUp({
                email: regEmail.toLowerCase(),
                password: regPassword,
                options: {
                    data: {
                        name: regName.trim(),
                        dob: regDob,
                        age: age,
                    }
                }
            })
            if (err) throw err

            const user = data.user
            // Store minimal user info locally
            localStorage.setItem('yojna_user', JSON.stringify({
                id: user?.id,
                email: regEmail.toLowerCase(),
                name: regName.trim(),
                age: age,
            }))
            localStorage.setItem('pending_name', regName.trim())
            navigate('/onboarding')
        } catch (err) {
            setError(err.message || 'Registration failed. Please try again.')
        } finally {
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
                <h1 className="signin-brand" style={{ textAlign: 'center', marginTop: 0 }}>
                    Yojna<span className="text-saffron">Setu</span>
                </h1>
                <p className="signin-sub" style={{ textAlign: 'center', marginBottom: 12 }}>
                    Government Schemes — For You
                </p>

                <div className="signin-tabs">
                    <button className={`signin-tab ${mode === 'signin' ? 'active' : ''}`} onClick={() => switchMode('signin')}>Sign In</button>
                    <button className={`signin-tab ${mode === 'register' ? 'active' : ''}`} onClick={() => switchMode('register')}>Create Account</button>
                </div>
                <div className="signin-divider" />

                {error && (
                    <div style={{ background: 'rgba(255,80,80,0.12)', border: '1px solid rgba(255,80,80,0.3)', borderRadius: 10, padding: '10px 14px', marginBottom: 12, color: '#ff6b6b', fontSize: 13 }}>
                        ⚠️ {error}
                    </div>
                )}

                {/* ── Sign In ── */}
                {mode === 'signin' && (
                    <form onSubmit={handleSignIn} className="signin-form">
                        <p className="signin-label">Email Address</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><Mail size={15} /></span>
                            <input type="email" placeholder="aapka@email.com" value={siEmail}
                                onChange={e => setSiEmail(e.target.value)} className="input-glass signin-input" autoFocus />
                        </div>
                        <p className="signin-label" style={{ marginTop: 4 }}>Password</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><Lock size={15} /></span>
                            <input type="password" placeholder="••••••••" value={siPassword}
                                onChange={e => setSiPassword(e.target.value)} className="input-glass signin-input" />
                        </div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn"
                            disabled={loading || !siEmail.includes('@') || !siPassword}>
                            {loading ? <span className="btn-spinner" /> : <><span>Sign In</span> <ArrowRight size={16} /></>}
                        </button>
                    </form>
                )}

                {/* ── Create Account ── */}
                {mode === 'register' && (
                    <form onSubmit={handleRegister} className="signin-form">
                        <p className="signin-label">Full Name</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><User size={15} /></span>
                            <input type="text" placeholder="e.g. Rajesh Kumar" value={regName}
                                onChange={e => setRegName(e.target.value)} className="input-glass signin-input" autoFocus />
                        </div>
                        <p className="signin-label" style={{ marginTop: 4 }}>Date of Birth</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><Calendar size={15} /></span>
                            <input type="date" value={regDob} max={new Date().toISOString().split('T')[0]}
                                onChange={e => setRegDob(e.target.value)} className="input-glass signin-input"
                                style={{ paddingLeft: 8 }} />
                        </div>
                        <p className="signin-label" style={{ marginTop: 4 }}>Email Address</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><Mail size={15} /></span>
                            <input type="email" placeholder="aapka@email.com" value={regEmail}
                                onChange={e => setRegEmail(e.target.value)} className="input-glass signin-input" />
                        </div>
                        <p className="signin-label" style={{ marginTop: 4 }}>Password</p>
                        <div className="signin-input-row">
                            <span className="signin-prefix"><Lock size={15} /></span>
                            <input type="password" placeholder="Min. 6 characters" value={regPassword}
                                onChange={e => setRegPassword(e.target.value)} className="input-glass signin-input" />
                        </div>
                        <button type="submit" className="btn btn-primary btn-lg signin-btn"
                            disabled={loading || !regName.trim() || !regDob || !regEmail.includes('@') || regPassword.length < 6}>
                            {loading ? <span className="btn-spinner" /> : <><span>Create Account</span> <ArrowRight size={16} /></>}
                        </button>
                    </form>
                )}

                <p className="signin-helper">By continuing, you agree to our <a href="#" className="text-saffron">Terms of Service</a></p>
                <div className="signin-alt">
                    <span className="text-muted">— or —</span>
                    <button className="btn btn-ghost signin-skip" onClick={() => navigate('/home')}>Continue as Guest (Demo)</button>
                </div>
            </div>

            {/* ── Jan Sahayak CTA ── */}
            <div className="signin-helper-cta" onClick={() => navigate('/register-helper')}>
                <div className="signin-helper-cta-left">
                    <div className="signin-helper-cta-icon">
                        <UserPlus size={18} />
                    </div>
                    <div>
                        <p className="signin-helper-cta-title">Want to help your community?</p>
                        <p className="signin-helper-cta-sub">Register as a Jan Sahayak volunteer</p>
                    </div>
                </div>
                <ChevronRight size={18} className="signin-helper-cta-arrow" />
            </div>
        </div>
    )
}
