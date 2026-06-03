import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, ArrowLeft, Check } from 'lucide-react'
import { supabase } from '../lib/supabase'

import './OnboardingPage.css'

const STEPS = [
    { id: 1, title: 'Your Profile', subtitle: 'Tell us about yourself' },
    { id: 2, title: 'Your Location', subtitle: 'Where are you from?' },
    { id: 3, title: 'Your Interests', subtitle: 'What help do you need?' },
]

const STATES = [
    'Andhra Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Delhi', 'Goa', 'Gujarat', 'Haryana',
    'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra',
    'Manipur', 'Meghalaya', 'Odisha', 'Punjab', 'Rajasthan', 'Tamil Nadu', 'Telangana',
    'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
]

const CATEGORIES = [
    { emoji: '🌾', label: 'Agriculture' },
    { emoji: '🏠', label: 'Housing' },
    { emoji: '❤️', label: 'Health' },
    { emoji: '🎓', label: 'Education' },
    { emoji: '👩', label: 'Women' },
    { emoji: '🛠️', label: 'Skill Dev' },
    { emoji: '👴', label: 'Pension' },
    { emoji: '💼', label: 'Business' },
]

export default function OnboardingPage() {
    const navigate = useNavigate()
    const [step, setStep] = useState(1)
    const [saving, setSaving] = useState(false)
    const [form, setForm] = useState({
        name: localStorage.getItem('pending_name') || '',
        dob: '', occupation: 'farmer', state: '', district: '', income: '', categories: []
    })

    const update = (field, val) => setForm(f => ({ ...f, [field]: val }))
    const toggleCat = (cat) => {
        setForm(f => ({
            ...f,
            categories: f.categories.includes(cat)
                ? f.categories.filter(c => c !== cat)
                : [...f.categories, cat]
        }))
    }

    const handleNext = async () => {
        if (step < 3) { setStep(s => s + 1); return }

        setSaving(true)
        const age = form.dob ? Math.floor((Date.now() - new Date(form.dob)) / (365.25 * 24 * 3600 * 1000)) : null
        const profile = {
            name: form.name,
            dob: form.dob,
            age,
            occupation: form.occupation,
            income: form.income,
            state: form.state,
            district: form.district,
            categories: form.categories,
        }
        localStorage.setItem('yojna_profile', JSON.stringify(profile))

        // ── Save to Supabase public.users ─────────────────────────
        try {
            const { data: { user } } = await supabase.auth.getUser()

            if (user) {
                // Update the row the trigger already created (matched by supabase_uid)
                const { error: upsertErr } = await supabase
                    .from('users')
                    .upsert({
                        supabase_uid: user.id,
                        email: user.email,
                        username: form.name.trim() || user.email.split('@')[0],
                        state: form.state,
                        language: 'hi-IN',
                    }, { onConflict: 'supabase_uid' })

                if (upsertErr) console.error('Supabase users update error:', upsertErr.message)

                // Also update user_profiles if it exists
                await supabase
                    .from('user_profiles')
                    .upsert({
                        // link by email since user_profiles may use the int id
                        occupation: form.occupation,
                        district: form.district,
                        annual_income_inr: form.income,
                    }, { onConflict: 'id' })
                    .eq?.('supabase_uid', user.id)   // no-op if column doesn't exist

                // Also update Supabase Auth metadata so it persists correctly
                await supabase.auth.updateUser({
                    data: {
                        name: form.name.trim(),
                        state: form.state,
                        occupation: form.occupation,
                        age,
                    }
                })
            }
        } catch (e) {
            console.error('Could not save profile to Supabase:', e)
        }

        // ── Fallback: also try Spring Boot if token exists ────────
        const token = localStorage.getItem('yojna_token')
        if (token) {
            fetch('/api/profile', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify(profile)
            }).catch(() => { })
        }

        localStorage.removeItem('pending_name')
        setSaving(false)
        navigate('/home')
    }


    const canProceed = () => {
        if (step === 1) return form.name.trim() && form.dob
        if (step === 2) return form.state
        return form.categories.length > 0
    }

    return (
        <div className="onboard-wrapper">
            <div className="onboard-bg-glow" />

            <div className="onboard-container">
                {/* Progress */}
                <div className="onboard-progress-row">
                    {STEPS.map((s, i) => (
                        <div key={s.id} className={`onboard-step-dot ${step > i ? 'done' : ''} ${step === i + 1 ? 'active' : ''}`}>
                            {step > i + 1 ? <Check size={12} /> : s.id}
                        </div>
                    ))}
                </div>
                <div className="onboard-progress-bar">
                    <div className="onboard-progress-fill" style={{ width: `${((step - 1) / (STEPS.length - 1)) * 100}%` }} />
                </div>

                {/* Card */}
                <div className="glass-card onboard-card">
                    <div className="onboard-header">
                        <h2 className="onboard-title">{STEPS[step - 1].title}</h2>
                        <p className="onboard-subtitle text-muted">{STEPS[step - 1].subtitle}</p>
                    </div>

                    {step === 1 && (
                        <div className="onboard-fields">
                            <div className="field-group">
                                <label className="field-label">Full Name</label>
                                <input className="input-glass" placeholder="e.g. Rajesh Kumar" value={form.name} onChange={e => update('name', e.target.value)} />
                            </div>
                            <div className="field-group">
                                <label className="field-label">Janm Tithi (Date of Birth)</label>
                                <input className="input-glass" type="date" value={form.dob}
                                    onChange={e => update('dob', e.target.value)}
                                    max={new Date().toISOString().split('T')[0]} />
                                {form.dob && (
                                    <p style={{ fontSize: 12, color: 'var(--saffron)', marginTop: 4 }}>
                                        Age: {form.dob ? Math.floor((new Date().getFullYear() - new Date(form.dob).getFullYear())) : ''} years
                                    </p>
                                )}
                            </div>
                            <div className="field-group">
                                <label className="field-label">Vyavsay (Occupation)</label>
                                <select className="input-glass" value={form.occupation} onChange={e => update('occupation', e.target.value)}>
                                    <option value="farmer">Kisan (Farmer)</option>
                                    <option value="labour">Majdoor (Daily Labour)</option>
                                    <option value="student">Vidyarthi (Student)</option>
                                    <option value="business">Vyapar (Business)</option>
                                    <option value="government">Sarkari Karmchari</option>
                                    <option value="homemaker">Gruhasth / Griha Nirmata</option>
                                    <option value="other">Anya (Other)</option>
                                </select>
                            </div>
                            <div className="field-group">
                                <label className="field-label">Varshik Aay (Annual Income)</label>
                                <select className="input-glass" value={form.income} onChange={e => update('income', e.target.value)}>
                                    <option value="">Select range</option>
                                    <option value="0-50k">Below ₹50,000</option>
                                    <option value="50k-1l">₹50,000 – ₹1 Lakh</option>
                                    <option value="1l-2.5l">₹1 Lakh – ₹2.5 Lakh</option>
                                    <option value="2.5l-5l">₹2.5 Lakh – ₹5 Lakh</option>
                                    <option value="5l+">Above ₹5 Lakh</option>
                                </select>
                            </div>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="onboard-fields">
                            <div className="field-group">
                                <label className="field-label">Rajya (State)</label>
                                <select className="input-glass" value={form.state} onChange={e => update('state', e.target.value)}>
                                    <option value="">Select your state</option>
                                    {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                                </select>
                            </div>
                            <div className="field-group">
                                <label className="field-label">Zila (District) <span className="text-subtle">(optional)</span></label>
                                <input className="input-glass" placeholder="e.g. Pune" value={form.district} onChange={e => update('district', e.target.value)} />
                            </div>
                            <div className="onboard-map-hint">
                                <span>📍</span>
                                <span className="text-muted text-sm">Schemes will be filtered based on your state</span>
                            </div>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="onboard-fields">
                            <p className="text-muted" style={{ fontSize: 13, marginBottom: 12 }}>
                                Select one or more categories:
                            </p>
                            <div className="onboard-cat-grid">
                                {CATEGORIES.map(c => (
                                    <button
                                        key={c.label}
                                        type="button"
                                        onClick={() => toggleCat(c.label)}
                                        className={`onboard-cat-btn ${form.categories.includes(c.label) ? 'selected' : ''}`}
                                    >
                                        <span className="cat-emoji">{c.emoji}</span>
                                        <span>{c.label}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Footer Buttons */}
                    <div className="onboard-footer">
                        {step > 1 && (
                            <button className="btn btn-ghost" onClick={() => setStep(s => s - 1)}>
                                <ArrowLeft size={16} /> Back
                            </button>
                        )}
                        <button
                            className="btn btn-primary"
                            onClick={handleNext}
                            disabled={!canProceed() || saving}
                            style={{ marginLeft: 'auto' }}
                        >
                            {saving ? <span className="btn-spinner" /> : step === 3 ? 'Get Started 🚀' : <><span>Continue</span> <ArrowRight size={16} /></>}
                        </button>
                    </div>
                </div>

                <p className="onboard-skip" onClick={() => navigate('/home')}>
                    Skip for now, set up later →
                </p>
            </div>
        </div>
    )
}
