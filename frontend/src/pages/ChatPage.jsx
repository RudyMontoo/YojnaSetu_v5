import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Mic, MicOff, VolumeX, Camera, Upload, Shield, Loader2, CheckCircle, X, Paperclip } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'
import './ChatPage.css'

const API = '/api'

const LANG_NAMES = {
    hi: 'Hindi', en: 'English', bn: 'Bengali', ta: 'Tamil',
    te: 'Telugu', kn: 'Kannada', mr: 'Marathi', gu: 'Gujarati', pa: 'Punjabi'
}

const DOC_TYPE_LABELS = {
    aadhaar:          { label: 'Aadhaar Card',     emoji: '🪪' },
    pan:              { label: 'PAN Card',          emoji: '💳' },
    voter_id:         { label: 'Voter ID Card',     emoji: '🗳️' },
    ration_card:      { label: 'Ration Card',       emoji: '🌾' },
    driving_licence:  { label: 'Driving Licence',   emoji: '🚗' },
    passport:         { label: 'Passport',          emoji: '📕' },
    disability_cert:  { label: 'Disability Certificate', emoji: '♿' },
    land_record:      { label: 'Land Record / Khasra',   emoji: '🗺️' },
    service_cert:     { label: 'Service Certificate',    emoji: '🎖️' },
}

/* Custom Sathi AI Avatar SVG */
const SathiAvatar = () => (
    <svg viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg" width="28" height="28">
        <circle cx="30" cy="22" r="10" fill="rgba(232,141,10,0.9)" />
        <circle cx="30" cy="22" r="6" fill="#0d0e1c" />
        <circle cx="27" cy="20" r="2" fill="#e88d0a" />
        <circle cx="33" cy="20" r="2" fill="#e88d0a" />
        <rect x="18" y="35" width="24" height="16" rx="4" fill="rgba(232,141,10,0.8)" />
        <rect x="22" y="40" width="4" height="6" rx="1" fill="#0d0e1c" />
        <rect x="34" y="40" width="4" height="6" rx="1" fill="#0d0e1c" />
        <line x1="30" y1="32" x2="30" y2="35" stroke="rgba(232,141,10,0.8)" strokeWidth="2" />
    </svg>
)

export default function ChatPage() {
    const navigate = useNavigate()
    const [messages, setMessages] = useState([
        {
            role: 'assistant',
            text: 'Namaste! 🙏 I am Sathi — your AI guide for government schemes.\n\n🎤 Tap the mic button to speak in any Indian language (Hindi, Tamil, Bengali, and more), or type your question below.',
            schemes: []
        }
    ])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [recording, setRecording] = useState(false)
    const [voiceMode, setVoiceMode] = useState(false)
    const [sessionId, setSessionId] = useState(null)
    const [audioPlaying, setAudioPlaying] = useState(false)
    const [dbSessionId, setDbSessionId] = useState(null)
    const [detectedLang, setDetectedLang] = useState('hi')
    const [showAttachMenu, setShowAttachMenu] = useState(false)

    // ── Doc scan state ─────────────────────────────────────────────────────
    const [docRequested, setDocRequested] = useState(null)  // e.g. 'aadhaar' | null
    const [scanLoading, setScanLoading] = useState(false)
    const [cameraOpen, setCameraOpen] = useState(false)
    const [cameraFacing, setCameraFacing] = useState('environment')
    const docFileRef = useRef()
    const videoRef = useRef()
    const canvasRef = useRef()
    const camStreamRef = useRef(null)

    // keep ref in sync so playAudio closure can read current voiceMode
    useEffect(() => { voiceModeRef.current = voiceMode }, [voiceMode])

    const bottomRef = useRef()
    const mediaRecRef = useRef(null)
    const chunksRef = useRef([])

    // Create/load session on mount
    useEffect(() => {
        initDbSession()
    }, [])

    const initDbSession = async () => {
        try {
            // First check if user is logged in
            const localUser = JSON.parse(localStorage.getItem('yojna_user'))
            if (!localUser) return

            // To keep things simple, generate a deterministic session 
            // ID based on user ID or email so they always resume their main thread
            const sid = `session-${localUser.email || 'guest'}`
            setDbSessionId(sid)

            // Chat history is kept in React state for the session.
            // (Backend /chat/session only supports DELETE to clear memory, no GET history endpoint)
        } catch (e) { console.error("Could not load history", e) }
    }

    // Notice we do NOT need to save messages individually anymore.
    // The AI Hub chat POST endpoint automatically saves user and assistant messages to SQLite.
    // We can remove saveMessage calls on the frontend to avoid duplicate data!
    // eslint-disable-next-line no-unused-vars
    const saveMessage = async (role, text) => {
        // Obsolete: Handled by backend `/api/chat` router now.
    }
    const audioRef = useRef(null)
    const voiceModeRef = useRef(false) // track voiceMode in closures

    const scrollBottom = () => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    useEffect(scrollBottom, [messages, loading])

    const playAudio = async (blob) => {
        if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        setAudioPlaying(true)
        audio.onended = async () => {
            setAudioPlaying(false)
            URL.revokeObjectURL(url)
            // Auto-listen: start mic again after each response if still in voice mode
            if (voiceModeRef.current) {
                await startRecordingAuto()
            }
        }
        audio.onerror = () => { setAudioPlaying(false); URL.revokeObjectURL(url) }
        await audio.play()
    }

    const stopAudio = () => {
        if (audioRef.current) { audioRef.current.pause(); audioRef.current = null }
        setAudioPlaying(false)
    }

    const addMsg = (role, text, extra = {}) =>
        setMessages(m => [...m, { role, text, schemes: [], ...extra }])

    // ── Doc scan handlers ────────────────────────────────────────────────────
    const openCameraForDoc = useCallback(async () => {
        setCameraOpen(true)
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: cameraFacing }
            })
            camStreamRef.current = stream
            if (videoRef.current) {
                videoRef.current.srcObject = stream
                videoRef.current.play()
            }
        } catch {
            setCameraOpen(false)
            // Fallback: open file picker
            docFileRef.current?.click()
        }
    }, [cameraFacing])

    const stopCamStream = useCallback(() => {
        if (camStreamRef.current) {
            camStreamRef.current.getTracks().forEach(t => t.stop())
            camStreamRef.current = null
        }
        setCameraOpen(false)
    }, [])

    const handleDocScan = useCallback(async (file) => {
        if (!file) return
        setScanLoading(true)
        addMsg('user', `📎 Document uploaded: ${file.name}`)

        try {
            const form = new FormData()
            form.append('file', file)
            if (dbSessionId) form.append('session_id', dbSessionId)

            const res = await fetch(`/ocr/scan`, { method: 'POST', body: form })
            if (!res.ok) {
                const err = await res.json().catch(() => ({}))
                throw new Error(err.detail || `Scan failed: ${res.status}`)
            }
            const data = await res.json()

            if (data.detected_ids?.length > 0) {
                const ids = data.detected_ids.map(d =>
                    `${d.doc_hint}: ${d.masked_value}`
                ).join(', ')
                addMsg('assistant', `✅ ${data.doc_type} scan successful!\n🔍 Detected: ${ids}\n\n🔒 Your document was not saved to our servers.`)
            } else {
                addMsg('assistant', `📄 ${data.doc_type} scanned but no unique ID was found. Please try a clearer image.`)
            }

            setDocRequested(null)  // hide upload bubble after scan
        } catch (err) {
            addMsg('assistant', `⚠️ Document scan failed: ${err.message}`)
        } finally {
            setScanLoading(false)
        }
    }, [dbSessionId])

    const captureDocFromCamera = useCallback(() => {
        const video = videoRef.current
        const canvas = canvasRef.current
        if (!video || !canvas) return
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        canvas.getContext('2d').drawImage(video, 0, 0)
        stopCamStream()
        canvas.toBlob(blob => {
            if (blob) handleDocScan(new File([blob], 'doc.jpg', { type: 'image/jpeg' }))
        }, 'image/jpeg', 0.92)
    }, [stopCamStream, handleDocScan])

    const startVoiceSession = async () => {
        setLoading(true)
        try {
            const form = new FormData()
            const res = await fetch(`/voice/conversation/start`, { method: 'POST', body: form })
            if (!res.ok) throw new Error(`${res.status}`)
            const sid = res.headers.get('X-Session-Id')
            const qText = decodeURIComponent(res.headers.get('X-Question-En') || '')
            const blob = await res.blob()
            setSessionId(sid)
            setVoiceMode(true)
            addMsg('assistant', qText, { voice: true })
            await playAudio(blob)
        } catch (err) {
            addMsg('assistant', `⚠️ Could not start voice session: ${err.message}`)
        } finally {
            setLoading(false)
        }
    }

    // Internal: starts mic without checking recording state — used by auto-listen
    const startRecordingAuto = async () => {
        try {
            // Brief pause so user knows Sathi finished before we listen
            await new Promise(r => setTimeout(r, 600))
            if (!voiceModeRef.current) return  // session ended while waiting
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
            chunksRef.current = []
            mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
            mr.onstop = () => stream.getTracks().forEach(t => t.stop())
            mr.start()
            mediaRecRef.current = mr
            setRecording(true)
        } catch {
            // silently fail — user can tap mic manually
        }
    }

    const startRecording = async () => {
        if (recording) return
        await startRecordingAuto()
    }

    const stopRecordingOnly = () => {
        if (!mediaRecRef.current || !recording) return
        const mr = mediaRecRef.current
        mr.onstop = null
        mr.stream?.getTracks().forEach(t => t.stop())
        mr.stop()
        setRecording(false)
    }

    const stopRecordingAndSend = () => {
        if (!mediaRecRef.current || !recording) return
        const mr = mediaRecRef.current
        mr.onstop = async () => {
            mr.stream?.getTracks().forEach(t => t.stop())
            setRecording(false)

            const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
            if (blob.size < 1000) {
                addMsg('assistant', '⚠️ Recording too short. Please speak a little longer.')
                return
            }

            setMessages(m => [...m, { role: 'user', text: '\uD83C\uDFA4 [Voice message]', schemes: [] }])
            setLoading(true)

            try {
                const form = new FormData()
                form.append('audio', blob, 'answer.webm')
                form.append('session_id', sessionId)
                const res = await fetch(`/voice/conversation/answer`, { method: 'POST', body: form })
                if (!res.ok) throw new Error(`${res.status}`)

                const transcript = decodeURIComponent(res.headers.get('X-Transcript') || '')
                const reply = decodeURIComponent(res.headers.get('X-Question-En') || '')
                const isDone = res.headers.get('X-Done') === 'true'
                const detLang = res.headers.get('X-Detected-Language') || 'hi'
                setDetectedLang(detLang)

                const audioBlob = await res.blob()

                if (transcript) {
                    setMessages(m => {
                        const updated = [...m]
                        updated[updated.length - 1] = { role: 'user', text: `\uD83C\uDFA4 "${transcript}"`, schemes: [] }
                        return updated
                    })
                }
                addMsg('assistant', reply, { voice: true })
                await playAudio(audioBlob)

                if (isDone) {
                    setVoiceMode(false)
                    setSessionId(null)
                    addMsg('assistant', '✅ Interview complete! Check the schemes above or ask more questions in chat.')
                }
            } catch (err) {
                addMsg('assistant', `\u26A0\uFE0F Voice error: ${err.message}`)
            } finally {
                setLoading(false)
            }
        }
        mr.stop()
    }

    const handleMicClick = async () => {
        if (recording) {
            stopRecordingAndSend()
        } else if (!voiceMode) {
            await startVoiceSession()
            await startRecording()
        } else {
            await startRecording()
        }
    }

    const sendMessage = async () => {
        if (!input.trim()) return
        const text = input.trim()
        addMsg('user', text)
        saveMessage('user', text)
        setInput('')
        setLoading(true)
        try {
            if (voiceMode && sessionId) {
                const res = await fetch(`/agent/answer`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, answer: text })
                })
                if (res.ok) {
                    const data = await res.json()
                    if (data.doc_requested) setDocRequested(data.doc_requested)
                    if (data.done) {
                        setVoiceMode(false)
                        setSessionId(null)
                        stopAudio()
                        addMsg('assistant', data.message || 'Interview complete!', { schemes: data.schemes || [] })
                    } else {
                        const reply = data.question_hi || data.question
                        addMsg('assistant', reply)
                    }
                } else {
                    addMsg('assistant', 'Backend error during interview.')
                }
            } else {
                const res = await fetch(`${API}/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, session_id: dbSessionId || 'frontend-demo' })
                })
                if (res.ok) {
                    const data = await res.json()
                    const reply = data.response || data.reply || data.message || 'Samajh gaya!'
                    // If agent signals a doc is needed, store it
                    if (data.doc_requested) setDocRequested(data.doc_requested)
                    setMessages(m => [...m, {
                        role: 'assistant',
                        text: reply,
                        schemes: data.matched_schemes || [],
                        docRequested: data.doc_requested || null,
                    }])
                } else {
                    const reply = 'Could not connect to backend. Browse schemes at /schemes.'
                    addMsg('assistant', reply)
                }
            }
        } catch {
            const reply = 'Backend appears to be offline. Click "Schemes" to browse available schemes.'
            addMsg('assistant', reply)
        } finally {
            setLoading(false)
        }
    }

    const handleFormSubmit = e => {
        e.preventDefault()
        if (input.trim()) {
            if (recording) stopRecordingOnly()
            sendMessage()
        } else if (recording) {
            stopRecordingAndSend()
        }
    }

    const handleKey = e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleFormSubmit(e)
        }
    }

    return (
        <div className="page-wrapper chat-wrapper">
            <Navbar />

            {voiceMode && (
                <div className="voice-mode-banner">
                    <span className="voice-pulse-dot" />
                    <span>
                        🌐 Detected: <strong>{LANG_NAMES[detectedLang] || detectedLang.toUpperCase()}</strong>
                        &nbsp;&bull; Tap 🎤 to speak
                    </span>
                    <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => { setVoiceMode(false); setSessionId(null); stopAudio() }}
                    >
                        End
                    </button>
                </div>
            )}

            {/* ── Inline camera overlay for doc capture ── */}
            {cameraOpen && (
                <div className="doc-camera-overlay">
                    <div className="doc-camera-header">
                        <Shield size={14} className="text-green" />
                        <span className="text-green" style={{ fontSize: 12 }}>Camera data is not saved</span>
                        <button className="btn btn-ghost btn-sm" onClick={stopCamStream} style={{ marginLeft: 'auto' }}>
                            <X size={16} />
                        </button>
                    </div>
                    <video ref={videoRef} className="doc-camera-feed" playsInline muted autoPlay />
                    <canvas ref={canvasRef} style={{ display: 'none' }} />
                    <div className="doc-camera-controls">
                        <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                                stopCamStream()
                                docFileRef.current?.click()
                            }}
                        >
                            <Upload size={14} /> File
                        </button>
                        <button
                            id="doc-capture-btn"
                            className="btn btn-primary capture-btn-sm"
                            onClick={captureDocFromCamera}
                        >
                            <Camera size={18} />
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={async () => {
                            stopCamStream()
                            const newFace = cameraFacing === 'environment' ? 'user' : 'environment'
                            setCameraFacing(newFace)
                            setCameraOpen(false)
                            setTimeout(() => openCameraForDoc(), 100)
                        }}>
                            🔄 Flip
                        </button>
                    </div>
                </div>
            )}

            <div className="chat-messages">
                {messages.map((msg, i) => (
                    <div key={i} className={`chat-bubble-row ${msg.role}`}>
                        {msg.role === 'assistant' && (
                            <div className="chat-avatar sathi-avatar-custom"><SathiAvatar /></div>
                        )}
                        <div className={`chat-bubble glass-card ${msg.role}`}>
                            {msg.voice && <span className="chat-voice-tag">🔊 Voice</span>}
                            <p className="chat-text" style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</p>
                            {msg.schemes && msg.schemes.length > 0 && (
                                <div className="chat-schemes">
                                    {msg.schemes.map(s => (
                                        <div
                                            key={s.id || s.name}
                                            className="chat-scheme-card"
                                            onClick={() => navigate(`/schemes/${s.id || 'scheme'}`, { state: s })}
                                            style={{ cursor: 'pointer' }}
                                        >
                                            <p className="scheme-card-title">{s.name}</p>
                                            <p className="scheme-card-benefit">{s.benefit}</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {/* ── Inline doc upload bubble ── */}
                            {msg.role === 'assistant' && msg.docRequested && (
                                <DocUploadBubble
                                    docType={msg.docRequested}
                                    scanLoading={scanLoading}
                                    onCamera={openCameraForDoc}
                                    onFile={() => docFileRef.current?.click()}
                                    onDismiss={() => setDocRequested(null)}
                                />
                            )}
                        </div>
                    </div>
                ))}

                {/* Active doc upload bubble at bottom if docRequested but last msg doesn't have it */}
                {docRequested && !scanLoading && messages[messages.length - 1]?.role !== 'user' && !messages[messages.length - 1]?.docRequested && (
                    <div className="chat-bubble-row assistant">
                        <div className="chat-avatar sathi-avatar-custom"><SathiAvatar /></div>
                        <div className="chat-bubble glass-card assistant">
                            <DocUploadBubble
                                docType={docRequested}
                                scanLoading={scanLoading}
                                onCamera={openCameraForDoc}
                                onFile={() => docFileRef.current?.click()}
                                onDismiss={() => setDocRequested(null)}
                            />
                        </div>
                    </div>
                )}

                {loading && (
                    <div className="chat-bubble-row assistant">
                        <div className="chat-avatar sathi-avatar-custom"><SathiAvatar /></div>
                        <div className="chat-bubble glass-card assistant">
                            <div className="typing-indicator">
                                <div className="typing-dot" />
                                <div className="typing-dot" />
                                <div className="typing-dot" />
                            </div>
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            {/* Hidden file input for doc uploads */}
            <input
                ref={docFileRef}
                type="file"
                accept="image/*,.pdf"
                hidden
                onChange={e => {
                    const f = e.target.files[0]
                    e.target.value = ''
                    if (f) handleDocScan(f)
                }}
            />

            <form className="chat-input-bar glass-card" onSubmit={handleFormSubmit}>
                <div style={{ position: 'relative' }}>
                    <button
                        type="button"
                        className="chat-mic-btn"
                        onClick={() => setShowAttachMenu(!showAttachMenu)}
                        title="Upload Document"
                        disabled={loading}
                        style={{ border: showAttachMenu ? '1px solid var(--saffron)' : '', background: showAttachMenu ? 'rgba(255, 107, 53, 0.15)' : '', color: showAttachMenu ? 'var(--saffron)' : '' }}
                    >
                        <Paperclip size={18} />
                    </button>
                    {showAttachMenu && (
                        <div className="glass-card" style={{ position: 'absolute', bottom: 'calc(100% + 12px)', left: 0, padding: '8px', display: 'flex', flexDirection: 'column', gap: '8px', zIndex: 100, minWidth: '120px', borderRadius: '12px', border: '1px solid var(--border-glass)', background: 'var(--bg-glass)', backdropFilter: 'blur(10px)' }}>
                            <button type="button" className="btn btn-ghost btn-sm" style={{ justifyContent: 'flex-start', width: '100%' }} onClick={() => { setShowAttachMenu(false); openCameraForDoc(); }}>
                                <Camera size={14} style={{ marginRight: '8px' }} /> Camera
                            </button>
                            <button type="button" className="btn btn-ghost btn-sm" style={{ justifyContent: 'flex-start', width: '100%' }} onClick={() => { setShowAttachMenu(false); docFileRef.current?.click(); }}>
                                <Upload size={14} style={{ marginRight: '8px' }} /> Gallery
                            </button>
                        </div>
                    )}
                </div>

                <button
                    type="button"
                    className={`chat-mic-btn ${recording ? 'recording' : voiceMode ? 'active' : ''}`}
                    onClick={handleMicClick}
                    title={recording ? 'Tap to stop & send' : voiceMode ? 'Tap to speak' : 'Start voice session'}
                    disabled={loading}
                >
                    {recording ? <MicOff size={18} /> : <Mic size={18} />}
                </button>

                {audioPlaying && (
                    <button type="button" className="chat-mic-btn active" onClick={stopAudio} title="Stop audio">
                        <VolumeX size={18} />
                    </button>
                )}

                <textarea
                    className="chat-input"
                    placeholder={recording ? '🔴 Recording… press Enter or tap 🎤 to send' : 'Ask about any government scheme…'}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    rows={1}
                />
                <button
                    type="submit"
                    className="chat-send-btn btn btn-primary btn-sm"
                    disabled={loading || (!recording && !input.trim())}
                >
                    <Send size={16} />
                </button>
            </form>

            <BottomNav />
        </div>
    )
}

// ── DocUploadBubble sub-component ────────────────────────────────────────────
function DocUploadBubble({ docType, scanLoading, onCamera, onFile, onDismiss }) {
    const info = DOC_TYPE_LABELS[docType] || { label: 'Document', emoji: '📄' }
    return (
        <div className="doc-upload-bubble">
            <div className="doc-bubble-header">
                <span className="doc-bubble-title">
                    {info.emoji} Upload {info.label}
                </span>
                <button className="btn btn-ghost btn-xs" onClick={onDismiss} title="Skip">
                    <X size={12} />
                </button>
            </div>
            {scanLoading ? (
                <div className="doc-bubble-scanning">
                    <Loader2 size={16} className="spin text-saffron" />
                    <span>Scanning…</span>
                </div>
            ) : (
                <div className="doc-bubble-actions">
                    <button
                        id="chat-doc-camera-btn"
                        className="btn btn-primary btn-sm doc-action-btn"
                        onClick={onCamera}
                    >
                        <Camera size={14} /> Camera
                    </button>
                    <button
                        id="chat-doc-upload-btn"
                        className="btn btn-ghost btn-sm doc-action-btn"
                        onClick={onFile}
                    >
                        <Upload size={14} /> Gallery
                    </button>
                </div>
            )}
            <div className="doc-bubble-privacy">
                <Shield size={10} />
                <span>Document will not be saved — only the ID will be detected</span>
            </div>
        </div>
    )
}
