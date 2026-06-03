import { useState, useRef, useCallback } from 'react'
import {
    Camera, Upload, CheckCircle, XCircle, HelpCircle,
    RefreshCw, Shield, FileText, Loader2, CameraOff, SwitchCamera, Lock
} from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './ScannerPage.css'

const API_BASE = '/api'

const DOC_LABELS = {
    aadhaar:         '🪪 Aadhaar Card',
    pan:             '💳 PAN Card',
    voter_id:        '🗳️ Voter ID',
    driving_licence: '🚗 Driving Licence',
    passport:        '📕 Passport',
    ration_card:     '🌾 Ration Card',
    bank_passbook:   '🏦 Bank Passbook',
    unknown:         '📄 Government Document',
}

const STEPS = ['Preprocessing image…', 'Running OCR engine…', 'Extracting unique IDs…', 'Masking sensitive data…']

export default function ScannerPage() {
    const [state, setState] = useState('idle')  // idle | camera | scanning | result | error
    const [result, setResult] = useState(null)
    const [error, setError] = useState('')
    const [stepIdx, setStepIdx] = useState(0)
    const [facingMode, setFacingMode] = useState('environment')  // environment = back cam

    const fileRef = useRef()
    const videoRef = useRef()
    const canvasRef = useRef()
    const streamRef = useRef(null)
    const stepTimerRef = useRef(null)

    // ── Step progress animation ──────────────────────────────────────────────
    const startStepAnimation = useCallback(() => {
        setStepIdx(0)
        let i = 0
        stepTimerRef.current = setInterval(() => {
            i++
            if (i < STEPS.length) setStepIdx(i)
            else clearInterval(stepTimerRef.current)
        }, 600)
    }, [])

    const stopStepAnimation = useCallback(() => {
        clearInterval(stepTimerRef.current)
    }, [])

    // ── API call ─────────────────────────────────────────────────────────────
    const scanFile = useCallback(async (file) => {
        setState('scanning')
        startStepAnimation()
        setError('')

        try {
            const form = new FormData()
            form.append('file', file)
            // No session_id for standalone scanner

            const res = await fetch(`/ocr/scan`, {
                method: 'POST',
                body: form,
            })

            stopStepAnimation()

            if (!res.ok) {
                const err = await res.json().catch(() => ({}))
                throw new Error(err.detail || `Server error ${res.status}`)
            }

            const data = await res.json()
            setResult(data)
            setState('result')
        } catch (err) {
            stopStepAnimation()
            setError(err.message || 'Document scan failed. Please try a clearer image.')
            setState('error')
        }
    }, [startStepAnimation, stopStepAnimation])

    // ── File upload ──────────────────────────────────────────────────────────
    const handleFile = (e) => {
        const file = e.target.files[0]
        if (!file) return
        e.target.value = ''  // reset so same file can be re-selected
        scanFile(file)
    }

    // ── Camera flow ──────────────────────────────────────────────────────────
    const openCamera = async () => {
        setState('camera')
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode, width: { ideal: 1920 }, height: { ideal: 1080 } }
            })
            streamRef.current = stream
            if (videoRef.current) {
                videoRef.current.srcObject = stream
                videoRef.current.play()
            }
        } catch (err) {
            console.error("Camera error:", err)
            setState('error')
            setError('Camera access denied. Please allow camera access or use file upload.')
        }
    }

    const flipCamera = async () => {
        stopStream()
        const newMode = facingMode === 'environment' ? 'user' : 'environment'
        setFacingMode(newMode)
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: newMode }
            })
            streamRef.current = stream
            if (videoRef.current) {
                videoRef.current.srcObject = stream
                videoRef.current.play()
            }
        } catch (e) {
            console.error("Failed to flip camera:", e)
        }
    }

    const captureFromCamera = () => {
        const video = videoRef.current
        const canvas = canvasRef.current
        if (!video || !canvas) return

        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        const ctx = canvas.getContext('2d')
        ctx.drawImage(video, 0, 0)

        stopStream()

        canvas.toBlob((blob) => {
            const file = new File([blob], 'scan.jpg', { type: 'image/jpeg' })
            scanFile(file)
        }, 'image/jpeg', 0.92)
    }

    const stopStream = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(t => t.stop())
            streamRef.current = null
        }
    }

    const reset = () => {
        stopStream()
        setState('idle')
        setResult(null)
        setError('')
    }

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="scanner-header">
                    <h1 className="scanner-title">Jan-Sahayak Lens 📷</h1>
                    <p className="text-muted scanner-sub">
                        Scan a document — unique ID will be detected automatically
                    </p>
                    {/* Privacy badge */}
                    <div className="privacy-badge">
                        <Shield size={14} className="privacy-icon" />
                        <span>Documents are never saved to our servers — processed in memory only</span>
                    </div>
                </div>

                {/* ── IDLE STATE ── */}
                {state === 'idle' && (
                    <div className="scanner-idle-layout">
                        {/* Left col: viewfinder */}
                        <div className="glass-card scanner-viewfinder" onClick={() => fileRef.current.click()}>
                            <div className="scanner-frame">
                                <div className="scanner-corner tl" />
                                <div className="scanner-corner tr" />
                                <div className="scanner-corner bl" />
                                <div className="scanner-corner br" />
                                <div className="scan-line" />
                                <div className="scanner-placeholder">
                                    <FileText size={48} className="text-muted" />
                                    <p className="text-muted scanner-placeholder-text">
                                        Tap here or use the buttons to upload
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Right col: actions + badges */}
                        <div className="scanner-actions-col">
                            <div className="scanner-actions">
                                <button
                                    id="scanner-camera-btn"
                                    className="btn btn-primary btn-lg scanner-upload-btn"
                                    onClick={openCamera}
                                >
                                    <Camera size={18} /> Scan with Camera
                                </button>
                                <button
                                    id="scanner-upload-btn"
                                    className="btn btn-ghost btn-lg scanner-upload-btn"
                                    onClick={() => fileRef.current.click()}
                                >
                                    <Upload size={18} /> Gallery / File Upload
                                </button>
                                <input
                                    ref={fileRef}
                                    type="file"
                                    accept="image/*,.pdf"
                                    hidden
                                    onChange={handleFile}
                                />
                                <p className="text-subtle scanner-note">
                                    Aadhaar, PAN, Voter ID, Ration Card, Passport, Driving Licence, PDF supported.
                                </p>
                            </div>

                            <div className="scanner-supported">
                                {['📄 Aadhaar', '💳 PAN', '🗳️ Voter ID', '🌾 Ration Card', '📕 Passport', '🚗 DL', '📑 PDF'].map(d => (
                                    <span key={d} className="badge badge-muted">{d}</span>
                                ))}
                            </div>
                        </div>
                    </div>
                )}


                {/* ── CAMERA STATE ── */}
                {state === 'camera' && (
                    <div className="camera-container glass-card">
                        <video ref={videoRef} className="camera-preview" playsInline muted autoPlay />
                        <canvas ref={canvasRef} style={{ display: 'none' }} />
                        <div className="camera-overlay">
                            <div className="camera-guide-frame">
                                <div className="scanner-corner tl" />
                                <div className="scanner-corner tr" />
                                <div className="scanner-corner bl" />
                                <div className="scanner-corner br" />
                            </div>
                            <p className="camera-hint text-muted">Keep document within the frame</p>
                        </div>
                        <div className="camera-controls">
                            <button className="btn btn-ghost btn-sm" onClick={reset}>
                                <CameraOff size={16} /> Cancel
                            </button>
                            <button
                                id="camera-capture-btn"
                                className="btn btn-primary capture-btn"
                                onClick={captureFromCamera}
                            >
                                <Camera size={20} />
                            </button>
                            <button className="btn btn-ghost btn-sm" onClick={flipCamera}>
                                <SwitchCamera size={16} /> Flip
                            </button>
                        </div>
                    </div>
                )}

                {/* ── SCANNING STATE ── */}
                {state === 'scanning' && (
                    <div className="scanner-loading glass-card">
                        <div className="scanner-spinner">
                            <Loader2 size={40} className="text-saffron spin" />
                        </div>
                        <p className="scanner-loading-text">Processing document…</p>
                        <div className="scan-steps">
                            {STEPS.map((step, i) => (
                                <div
                                    key={step}
                                    className={`scan-step ${i < stepIdx ? 'done' : i === stepIdx ? 'active' : ''}`}
                                >
                                    {i < stepIdx
                                        ? <CheckCircle size={14} className="text-green" />
                                        : i === stepIdx
                                        ? <Loader2 size={14} className="spin" />
                                        : <div className="step-dot" />
                                    }
                                    <span>{step}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── RESULT STATE ── */}
                {state === 'result' && result && (
                    <>
                        {/* Doc type + validity */}
                        <div className="glass-card glass-card-glow scanner-result-header">
                            <div className="scanner-result-badge">
                                {result.validity?.is_valid
                                    ? <CheckCircle size={20} className="text-green" />
                                    : <HelpCircle size={20} className="text-amber" />
                                }
                                <span className={`badge ${result.validity?.is_valid ? 'badge-green' : 'badge-amber'}`}>
                                    {result.validity?.is_valid ? 'Valid Document' : 'Document Partially Read'}
                                </span>
                            </div>
                            <h2 className="scanner-doc-type">
                                {DOC_LABELS[result.detected_ids?.[0]?.id_type] || result.doc_type}
                            </h2>
                            {result.page_count > 1 && (
                                <p className="text-muted" style={{ fontSize: 13 }}>
                                    {result.page_count} pages scanned
                                </p>
                            )}
                        </div>

                        {/* Detected IDs — masked values */}
                        {result.detected_ids?.length > 0 && (
                            <div className="glass-card scanner-ids-card">
                                <h3 className="scanner-fields-title">
                                    🔍 Detected Unique IDs
                                </h3>
                                <p className="id-privacy-note">
                                    <Lock size={10} />
                                    Only last 4 digits shown — raw data is never saved
                                </p>
                                {result.detected_ids.map((id, i) => (
                                    <div key={i} className="scanner-id-row">
                                        <div className="id-type-label">
                                            <span className="badge badge-muted">{id.doc_hint}</span>
                                            <span
                                                className="confidence-dot"
                                                title={`Confidence: ${Math.round(id.confidence * 100)}%`}
                                                style={{
                                                    background: id.confidence >= 0.85
                                                        ? '#22c55e'
                                                        : id.confidence >= 0.65
                                                        ? '#f59e0b'
                                                        : '#ef4444'
                                                }}
                                            />
                                        </div>
                                        <div className="masked-id-display">
                                            {id.masked_value}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* No IDs found */}
                        {(!result.detected_ids || result.detected_ids.length === 0) && (
                            <div className="glass-card scanner-missing">
                                <h3 className="scanner-fields-title">
                                    <HelpCircle size={16} className="text-amber" /> Koi ID Nahi Mili
                                </h3>
                                <p className="text-muted" style={{ fontSize: 14 }}>
                                    Document may be unclear. Try again in better lighting.
                                </p>
                            </div>
                        )}

                        {/* Validity details */}
                        <div className="glass-card scanner-validity">
                            <div className="validity-row">
                                <span className="validity-label">Official Seal</span>
                                {result.validity?.has_official_seal
                                    ? <CheckCircle size={16} style={{ color: '#4ade80' }} />
                                    : <XCircle size={16} className="text-subtle" />
                                }
                            </div>
                            <div className="validity-row">
                                <span className="validity-label">Expiry Info</span>
                                {result.validity?.has_expiry_info
                                    ? <CheckCircle size={16} style={{ color: '#4ade80' }} />
                                    : <XCircle size={16} className="text-subtle" />
                                }
                            </div>
                            <div className="validity-row">
                                <span className="validity-label">OCR Confidence</span>
                                <span className="confidence-pct">
                                    {Math.round((result.validity?.confidence || 0) * 100)}%
                                </span>
                            </div>
                        </div>

                        <button className="btn btn-ghost scanner-reset-btn" onClick={reset}>
                            <RefreshCw size={16} /> Scan Again
                        </button>
                    </>
                )}

                {/* ── ERROR STATE ── */}
                {state === 'error' && (
                    <div className="glass-card scanner-error">
                        <XCircle size={36} className="text-red" />
                        <p className="scanner-loading-text">Scan Failed</p>
                        <p className="text-muted" style={{ fontSize: 14 }}>{error}</p>
                        <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={reset}>
                            <RefreshCw size={16} /> Try Again
                        </button>
                    </div>
                )}

            </main>
            <BottomNav />
        </div>
    )
}
