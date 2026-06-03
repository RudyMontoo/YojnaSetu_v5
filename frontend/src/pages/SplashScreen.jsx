import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './SplashScreen.css'

export default function SplashScreen() {
    const navigate = useNavigate()

    useEffect(() => {
        const timer = setTimeout(() => navigate('/signin'), 2800)
        return () => clearTimeout(timer)
    }, [navigate])

    return (
        <div className="splash-wrapper">
            {/* Glow rings */}
            <div className="splash-glow-outer" />
            <div className="splash-glow-inner" />

            <div className="splash-content">
                {/* Logo */}
                <div className="splash-logo">
                    <div className="splash-logo-circle">
                        <img src="/logo.png" alt="Yojna Setu" className="splash-logo-img" />
                    </div>
                    <div className="splash-logo-ring" />
                </div>

                {/* Brand */}
                <h1 className="splash-brand">
                    Yojna<span className="text-saffron">Setu</span>
                </h1>
                <p className="splash-tagline-sub">JAN JAN KO YOJANA SE JODO</p>

                {/* Language row */}
                <div className="splash-lang-row">
                    {['हिंदी', 'English', 'বাংলা', 'தமிழ்', 'తెలుగు'].map((lang, i) => (
                        <span key={i} className={`splash-lang-chip ${i === 0 ? 'active' : ''}`}>{lang}</span>
                    ))}
                </div>

                {/* Loading */}
                <div className="splash-loading">
                    <div className="splash-spinner" />
                    <span className="splash-loading-text">Initialising...</span>
                </div>

                <span className="splash-version">VER 2.4.0</span>
            </div>
        </div>
    )
}
