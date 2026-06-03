import { useState } from 'react'
import { X, Youtube, MapPin, Monitor, Users } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import './ApplyMethodModal.css'

/**
 * ApplyMethodModal — shown when user clicks "Apply Now" on a scheme.
 * Lets them choose: Online (YouTube tutorial) or Offline (Jan Sahayak finder).
 *
 * Props:
 *   scheme     — { name, applyUrl, applyPortal, youtubeQuery? }
 *   onClose    — fn to close modal
 */
export default function ApplyMethodModal({ scheme, onClose }) {
    const navigate = useNavigate()
    const [mode, setMode] = useState(null)  // null | 'online' | 'offline'

    // Derive a YouTube search URL if no specific video given
    const ytQuery = scheme.youtubeQuery || `${scheme.name} apply online tutorial India`
    const ytSearchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(ytQuery)}`

    const handleOffline = () => {
        onClose()
        navigate(`/helpers?scheme=${encodeURIComponent(scheme.name)}`)
    }

    return (
        <div className="apply-modal-overlay" onClick={onClose}>
            <div className="apply-modal-card glass-card" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="apply-modal-header">
                    <div>
                        <p className="apply-modal-eyebrow">How would you like to apply?</p>
                        <h2 className="apply-modal-title">{scheme.shortName || scheme.name}</h2>
                    </div>
                    <button className="btn btn-ghost btn-sm apply-modal-close" onClick={onClose}>
                        <X size={18} />
                    </button>
                </div>

                {/* Mode selector */}
                {!mode && (
                    <div className="apply-method-grid">
                        <button className="apply-method-card online" onClick={() => setMode('online')}>
                            <div className="apply-method-icon">
                                <Monitor size={32} />
                            </div>
                            <h3>Apply Online</h3>
                            <p>Watch a step-by-step video tutorial and apply directly on the official portal.</p>
                            <span className="apply-method-badge">Instant</span>
                        </button>

                        <button className="apply-method-card offline" onClick={handleOffline}>
                            <div className="apply-method-icon">
                                <Users size={32} />
                            </div>
                            <h3>Get Offline Help</h3>
                            <p>Find a Jan Sahayak near you who will help you fill and submit the form in person.</p>
                            <span className="apply-method-badge assisted">Assisted</span>
                        </button>
                    </div>
                )}

                {/* Online mode — YouTube embed + portal link */}
                {mode === 'online' && (
                    <div className="apply-online-content">
                        <button className="btn btn-ghost btn-sm apply-back-btn" onClick={() => setMode(null)}>
                            ← Back
                        </button>
                        <div className="apply-yt-container">
                            <div className="apply-yt-placeholder">
                                <Youtube size={48} className="yt-icon" />
                                <p className="apply-yt-text">Video Tutorial</p>
                                <p className="text-muted" style={{ fontSize: 13 }}>
                                    Search: "{scheme.name} apply online"
                                </p>
                                <a
                                    href={ytSearchUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="btn btn-primary btn-sm"
                                    style={{ marginTop: 12 }}
                                >
                                    <Youtube size={14} /> Watch on YouTube
                                </a>
                            </div>
                        </div>
                        <div className="apply-online-actions">
                            <a
                                href={scheme.applyUrl}
                                target="_blank"
                                rel="noreferrer"
                                className="btn btn-primary btn-lg apply-portal-btn"
                            >
                                <Monitor size={16} /> Open Official Portal
                            </a>
                            <p className="text-subtle" style={{ fontSize: 12, marginTop: 8 }}>
                                {scheme.applyPortal}
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
