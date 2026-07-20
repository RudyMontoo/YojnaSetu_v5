import { useState, useRef, useCallback } from 'react'
import {
    Camera, Upload, CheckCircle, XCircle, HelpCircle,
    RefreshCw, Shield, FileText, Loader2, CameraOff, SwitchCamera, Lock,
    AlertTriangle, UserCheck
} from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { Reveal } from '../components/motion'
import { Sparkles } from 'lucide-react'
import { ai, gateway } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'
import './ScannerPage.css'

const UI = {
    tag: 'Agent 4 · Document Seva', title: 'Jan-Sahayak Lens',
    sub: 'Scan a document — we verify it & auto-fill your profile',
    privacy: 'Documents are never saved to our servers — processed in memory only',
    // repurposed: verify + autofill
    stVerified: 'Document verified ✓', stMismatch: 'Details do not match your profile',
    stNoProfile: 'Read successfully', stUnreadable: 'Could not read clearly',
    chkChecksum: 'Valid Aadhaar number', chkName: 'Name matches your profile', chkDob: 'Date of birth matches',
    weRead: 'We read from your document:', nameLabel: 'Name', dobLabel: 'Date of Birth',
    saveToProfile: 'Save to my profile', saving: 'Saving…', savedOk: 'Saved to your profile ✓ — no need to type it again.',
    okToApply: 'You can use this document to apply.',
    tapUpload: 'Tap here or use the buttons to upload', scanCamera: 'Scan with Camera',
    galleryUpload: 'Gallery / File Upload',
    supported: 'Aadhaar, PAN, Voter ID, Ration Card, Passport, Driving Licence, PDF supported.',
    keepInFrame: 'Keep document within the frame', cancel: 'Cancel', flip: 'Flip',
    processing: 'Processing document…', validDoc: 'Valid Document', partialDoc: 'Document Partially Read',
    pagesScanned: 'pages scanned', detectedIds: '🔍 Detected Unique IDs',
    only4: 'Only last 4 digits shown — raw data is never saved',
    noId: 'Koi ID Nahi Mili', unclear: 'Document may be unclear. Try again in better lighting.',
    officialSeal: 'Official Seal', expiryInfo: 'Expiry Info', ocrConfidence: 'OCR Confidence',
    scanAgain: 'Scan Again', scanFailed: 'Scan Failed', tryAgain: 'Try Again',
}

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
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)

    // Auto-fill the citizen's profile from the read-back fields — scan once,
    // never type a 12-digit Aadhaar again. Goes through Spring (encrypts PII).
    const saveToProfile = async (autofill) => {
        setSaving(true)
        try {
            await gateway.updateProfile(autofill)
            setSaved(true)
        } catch (err) {
            setError(err.message || 'Could not save to profile')
        } finally { setSaving(false) }
    }
    const [stepIdx, setStepIdx] = useState(0)
    const [facingMode, setFacingMode] = useState('environment')  // environment = back cam

    const fileRef = useRef()
    const videoRef = useRef()
    const canvasRef = useRef()
    const streamRef = useRef(null)
    const stepTimerRef = useRef(null)
    const tr = useAutoTranslate([
        ...Object.values(UI), ...STEPS, ...Object.values(DOC_LABELS), error,
    ].filter(Boolean))

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
            // Repurposed: verify the document + get read-back fields to auto-fill
            // the profile (needs the citizen cookie — this is a logged-in tool).
            const data = await ai.verifyDocument(file)
            stopStepAnimation()
            setResult(data)
            setState('result')
        } catch (err) {
            stopStepAnimation()
            setError(err.status === 401 || err.status === 403
                ? 'Please login first to verify a document.'
                : (err.message || 'Document scan failed. Please try a clearer image.'))
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
        setSaved(false)
    }

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="scanner-header">
                    <div className="sathi-tag" style={{ position: 'static', display: 'inline-flex', marginBottom: 8 }}><Sparkles size={10} /> {tr(UI.tag)}</div>
                    <h1 className="scanner-title font-display">{tr(UI.title)}</h1>
                    <p className="text-muted scanner-sub">
                        {tr(UI.sub)}
                    </p>
                    {/* Privacy badge */}
                    <div className="privacy-badge">
                        <Shield size={14} className="privacy-icon" />
                        <span>{tr(UI.privacy)}</span>
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
                                        {tr(UI.tapUpload)}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Right col: actions + badges */}
                        <div className="scanner-actions-col">
                            <div className="scanner-actions">
                                <button
                                    id="scanner-camera-btn"
                                    className="btn btn-primary btn-lg scanner-upload-btn btn-aarti"
                                    onClick={openCamera}
                                >
                                    <Camera size={18} /> {tr(UI.scanCamera)}
                                </button>
                                <button
                                    id="scanner-upload-btn"
                                    className="btn btn-ghost btn-lg scanner-upload-btn"
                                    onClick={() => fileRef.current.click()}
                                >
                                    <Upload size={18} /> {tr(UI.galleryUpload)}
                                </button>
                                <input
                                    ref={fileRef}
                                    type="file"
                                    accept="image/*,.pdf"
                                    hidden
                                    onChange={handleFile}
                                />
                                <p className="text-subtle scanner-note">
                                    {tr(UI.supported)}
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
                            <p className="camera-hint text-muted">{tr(UI.keepInFrame)}</p>
                        </div>
                        <div className="camera-controls">
                            <button className="btn btn-ghost btn-sm" onClick={reset}>
                                <CameraOff size={16} /> {tr(UI.cancel)}
                            </button>
                            <button
                                id="camera-capture-btn"
                                className="btn btn-primary capture-btn btn-aarti"
                                onClick={captureFromCamera}
                            >
                                <Camera size={20} />
                            </button>
                            <button className="btn btn-ghost btn-sm" onClick={flipCamera}>
                                <SwitchCamera size={16} /> {tr(UI.flip)}
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
                        <p className="scanner-loading-text">{tr(UI.processing)}</p>
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
                                    <span>{tr(step)}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── RESULT STATE (verify + auto-fill) ── */}
                {state === 'result' && result && (() => {
                    const ok = result.status === 'verified'
                    const mismatch = result.status === 'mismatch'
                    const Row = ({ label, val }) => val === null || val === undefined ? null : (
                        <div className="validity-row">
                            <span className="validity-label">{tr(label)}</span>
                            {val ? <CheckCircle size={16} style={{ color: '#4ade80' }} />
                                 : <AlertTriangle size={16} style={{ color: '#f59e0b' }} />}
                        </div>
                    )
                    return (
                    <>
                        {/* Verdict header */}
                        <div className="glass-card glass-card-glow scanner-result-header">
                            <div className="scanner-result-badge">
                                {ok ? <CheckCircle size={20} className="text-green" />
                                    : mismatch ? <AlertTriangle size={20} style={{ color: '#f59e0b' }} />
                                    : <HelpCircle size={20} className="text-amber" />}
                                <span className={`badge ${ok ? 'badge-green' : mismatch ? 'badge-amber' : 'badge-muted'}`}>
                                    {tr(ok ? UI.stVerified : mismatch ? UI.stMismatch
                                        : result.status === 'unreadable' ? UI.stUnreadable : UI.stNoProfile)}
                                </span>
                            </div>
                            <h2 className="scanner-doc-type">{tr(result.doc_type_label || result.doc_type)}</h2>
                            {result.masked_id && <p className="text-muted" style={{ fontSize: 13 }}><Lock size={10} /> {result.masked_id}</p>}
                            {result.ok_to_apply && <p className="text-green" style={{ fontSize: 13, marginTop: 4 }}>{tr(UI.okToApply)}</p>}
                        </div>

                        {/* Checks the citizen can't self-verify */}
                        {(result.checksum_valid !== null || result.name_matches_profile !== null || result.dob_matches_profile !== null) && (
                            <div className="glass-card scanner-validity">
                                <Row label={UI.chkChecksum} val={result.checksum_valid} />
                                <Row label={UI.chkName} val={result.name_matches_profile} />
                                <Row label={UI.chkDob} val={result.dob_matches_profile} />
                            </div>
                        )}

                        {/* Warnings (Hinglish) */}
                        {result.warnings?.length > 0 && (
                            <div className="glass-card" style={{ padding: 14 }}>
                                {result.warnings.map((w, i) => (
                                    <p key={i} style={{ fontSize: 13, marginBottom: 6, display: 'flex', gap: 6 }}>
                                        <AlertTriangle size={14} style={{ color: '#f59e0b', flexShrink: 0, marginTop: 2 }} /> {tr(w)}
                                    </p>
                                ))}
                            </div>
                        )}

                        {/* Read-back → save to profile (scan once, never type again) */}
                        {result.autofill && Object.keys(result.autofill).length > 0 && (
                            <div className="glass-card" style={{ padding: 16 }}>
                                <p className="scanner-fields-title" style={{ marginBottom: 8 }}>{tr(UI.weRead)}</p>
                                {result.autofill.name && <p style={{ fontSize: 14 }}><b>{tr(UI.nameLabel)}:</b> {result.autofill.name}</p>}
                                {result.autofill.dob && <p style={{ fontSize: 14 }}><b>{tr(UI.dobLabel)}:</b> {result.autofill.dob}</p>}
                                {saved ? (
                                    <p className="text-green" style={{ fontSize: 13.5, marginTop: 10 }}><CheckCircle size={13} /> {tr(UI.savedOk)}</p>
                                ) : (
                                    <button className="btn btn-primary btn-aarti btn-sm" style={{ marginTop: 12 }}
                                            disabled={saving} onClick={() => saveToProfile(result.autofill)}>
                                        {saving ? <><Loader2 size={14} className="spin" /> {tr(UI.saving)}</>
                                                : <><UserCheck size={14} /> {tr(UI.saveToProfile)}</>}
                                    </button>
                                )}
                            </div>
                        )}

                        <button className="btn btn-ghost scanner-reset-btn" onClick={reset}>
                            <RefreshCw size={16} /> {tr(UI.scanAgain)}
                        </button>
                    </>
                    )
                })()}

                {/* ── ERROR STATE ── */}
                {state === 'error' && (
                    <div className="glass-card scanner-error">
                        <XCircle size={36} className="text-red" />
                        <p className="scanner-loading-text">{tr(UI.scanFailed)}</p>
                        <p className="text-muted" style={{ fontSize: 14 }}>{tr(error)}</p>
                        <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={reset}>
                            <RefreshCw size={16} /> {tr(UI.tryAgain)}
                        </button>
                    </div>
                )}

            </main>
            <BottomNav />
        </div>
    )
}
