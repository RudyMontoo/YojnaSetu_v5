import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck, ArrowRight, Eye, EyeOff } from 'lucide-react'
import './HelperLoginPage.css'

export default function HelperLoginPage() {
    const navigate   = useNavigate()
    const inputRef   = useRef(null)
    const [code, setCode]       = useState('')
    const [show, setShow]       = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError]     = useState('')

    const formatted = (v) => {
        // Auto-format as user types: YS-HELP-000000
        const clean = v.toUpperCase().replace(/[^A-Z0-9]/g, '')
        if (clean.startsWith('YSHELP')) {
            const digits = clean.slice(6)
            return `YS-HELP-${digits.slice(0, 6)}`
        }
        return v.toUpperCase()
    }

    const handleChange = (e) => {
        setError('')
        setCode(formatted(e.target.value))
    }

    const login = async () => {
        if (!code.match(/^YS-HELP-\d{6}$/)) {
            setError('Enter a valid Helper ID (format: YS-HELP-XXXXXX)')
            return
        }
        setLoading(true)
        setError('')
        try {
            const fd = new FormData()
            fd.append('helper_code', code)
            const res  = await fetch('/sahayak/helper/login', { method: 'POST', body: fd })
            const data = await res.json()
            if (!res.ok) throw new Error(data.detail || 'Login failed')

            // Store helper session in localStorage
            localStorage.setItem('yojna_helper', JSON.stringify(data.helper))
            navigate('/helper-dashboard')
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="helper-login-wrapper">
            <div className="helper-login-bg-glow" />

            <div className="helper-login-card glass-card">
                {/* Logo + branding */}
                <div className="helper-login-logo">
                    <div className="helper-login-shield">
                        <ShieldCheck size={32} />
                    </div>
                </div>
                <h1 className="helper-login-brand">
                    Jan Sahayak <span className="text-saffron">Portal</span>
                </h1>
                <p className="helper-login-sub">
                    Log in with your unique Helper ID to access your dashboard.
                </p>

                <div className="helper-login-divider" />

                {error && (
                    <div className="helper-login-error">
                        ⚠️ {error}
                    </div>
                )}

                <div className="helper-login-field">
                    <label className="field-label">Your Helper ID</label>
                    <div className="helper-login-input-row">
                        <div className="helper-login-prefix">
                            <ShieldCheck size={15} />
                        </div>
                        <input
                            ref={inputRef}
                            className="input-glass helper-login-input"
                            type={show ? 'text' : 'password'}
                            placeholder="YS-HELP-XXXXXX"
                            value={code}
                            onChange={handleChange}
                            maxLength={14}
                            onKeyDown={e => e.key === 'Enter' && login()}
                            autoFocus
                        />
                        <button
                            className="helper-login-toggle"
                            type="button"
                            onClick={() => setShow(s => !s)}
                            title={show ? 'Hide ID' : 'Show ID'}
                        >
                            {show ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                    </div>
                    <p className="helper-login-hint">
                        This ID was emailed to you after your registration was verified.
                    </p>
                </div>

                <button
                    className="btn btn-primary btn-lg helper-login-btn"
                    onClick={login}
                    disabled={loading || !code}
                >
                    {loading
                        ? <span className="btn-spinner" />
                        : <><span>Access Dashboard</span> <ArrowRight size={16} /></>
                    }
                </button>

                <div className="helper-login-footer">
                    <span className="text-muted">Not a helper yet?</span>
                    <button className="btn btn-ghost helper-login-reg-link"
                        onClick={() => navigate('/register-helper')}>
                        Register as Jan Sahayak →
                    </button>
                </div>

                <div className="helper-login-citizen-link">
                    <button className="btn btn-ghost" onClick={() => navigate('/signin')}
                        style={{ fontSize: 13 }}>
                        ← Citizen Login
                    </button>
                </div>
            </div>
        </div>
    )
}
