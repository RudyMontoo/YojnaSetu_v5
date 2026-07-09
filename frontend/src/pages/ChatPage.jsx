import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Mic, MicOff, Camera, Upload, Shield, Loader2, CheckCircle, X, Paperclip } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Navbar, BottomNav } from '../components/Navbar'
import { BubbleIn } from '../components/motion'
import AgentCouncil from '../components/AgentCouncil'
import { gateway } from '../lib/api'
import { useLang } from '../lib/i18n'
import '../components/components.css'
import './ChatPage.css'

const API = '/api'

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
    const { t, lang } = useLang()
    const [messages, setMessages] = useState([
        { role: 'assistant', text: t('chat.greeting'), schemes: [] }
    ])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [voiceMode, setVoiceMode] = useState(false)       // live voice call active
    const [userSpeaking, setUserSpeaking] = useState(false) // VAD: citizen talking now
    const [botSpeaking, setBotSpeaking] = useState(false)   // Sathi's reply audio playing
    const [dbSessionId, setDbSessionId] = useState(null)
    const [showAttachMenu, setShowAttachMenu] = useState(false)
    const [agentSplash, setAgentSplash] = useState(0)   // increments each time an agent finishes

    // ── Doc scan state ─────────────────────────────────────────────────────
    const [docRequested, setDocRequested] = useState(null)  // e.g. 'aadhaar' | null
    const [scanLoading, setScanLoading] = useState(false)
    const [cameraOpen, setCameraOpen] = useState(false)
    const [cameraFacing, setCameraFacing] = useState('environment')
    const docFileRef = useRef()
    const videoRef = useRef()
    const canvasRef = useRef()
    const camStreamRef = useRef(null)

    const bottomRef = useRef()
    const voiceClientRef = useRef(null)  // live PipecatClient (one per call)

    // hang up cleanly if the user navigates away mid-call
    useEffect(() => () => { voiceClientRef.current?.disconnect?.() }, [])

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
    const sessionIdRef = useRef(null)  // orchestrator conversation session
    const wsRef = useRef(null)         // streaming chat socket (one per session)

    useEffect(() => () => wsRef.current?.close(), [])

    // if the user switches language before chatting, re-render the greeting in it
    useEffect(() => {
        setMessages(m => (m.length === 1 && m[0].role === 'assistant')
            ? [{ role: 'assistant', text: t('chat.greeting'), schemes: [] }] : m)
    }, [t])

    const scrollBottom = () => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    useEffect(scrollBottom, [messages, loading])

    const addMsg = (role, text, extra = {}) =>
        setMessages(m => [...m, { role, text, schemes: [], ...extra }])

    const saveScheme = async (s) => {
        try {
            await gateway.createApplication(s.code)
            addMsg('assistant', `"${s.name}" saved to My Applications. Track it from the Status tab.`)
        } catch (err) {
            addMsg('assistant', err.status === 409
                ? `"${s.name}" is already in your applications.`
                : err.status === 401 || err.status === 403
                    ? 'Please login first to save schemes.'
                    : `Could not save: ${err.message}`)
        }
    }

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

    // ── v5.0 LIVE voice: streaming call to /ws/voice/{session_id} ────────────
    // Real-time pipeline (Pipecat protobuf): mic streams continuously, Sarvam's
    // server-side VAD detects when the citizen stops talking, the transcript
    // runs through the SAME orchestrator session as typed chat, and the spoken
    // reply streams back — with barge-in (speak to interrupt Sathi mid-reply).
    // The turn-based /voice/conversation/* endpoints remain server-side as a
    // fallback surface, but this client is live-first.

    const upsertVoiceUserBubble = (text, final) => {
        setMessages(m => {
            const last = m[m.length - 1]
            const bubble = { role: 'user', text: `\u{1F3A4} ${final ? `"${text}"` : text}`, schemes: [], voicePartial: !final }
            return last?.voicePartial ? [...m.slice(0, -1), bubble] : [...m, bubble]
        })
    }

    const appendBotVoiceText = (chunk) => {
        if (!chunk) return
        setMessages(m => {
            const last = m[m.length - 1]
            if (last?.voiceStreaming) {
                return [...m.slice(0, -1), { ...last, text: (last.text + ' ' + chunk).replace(/\s+/g, ' ') }]
            }
            return [...m, { role: 'assistant', text: chunk, schemes: [], voice: true, voiceStreaming: true }]
        })
    }

    const finalizeBotVoiceBubble = () => {
        setMessages(m => {
            const last = m[m.length - 1]
            return last?.voiceStreaming ? [...m.slice(0, -1), { ...last, voiceStreaming: false }] : m
        })
        setAgentSplash(n => n + 1)
    }

    const endLiveVoice = async () => {
        const client = voiceClientRef.current
        voiceClientRef.current = null
        setVoiceMode(false); setUserSpeaking(false); setBotSpeaking(false)
        try { await client?.disconnect?.() } catch { /* already closed */ }
    }

    const startLiveVoice = async () => {
        setLoading(true)
        try {
            // Lazy chunk: the Pipecat client (~400KB) loads only when a call starts
            const { createVoiceClient } = await import('../lib/voiceClient')
            const client = createVoiceClient({
                sessionId: ensureSessionId(),
                onUserTranscript: (data) => upsertVoiceUserBubble(data.text, data.final),
                onBotText: appendBotVoiceText,
                onUserSpeaking: setUserSpeaking,
                onBotSpeaking: (speaking) => {
                    setBotSpeaking(speaking)
                    if (!speaking) finalizeBotVoiceBubble()
                },
                onDisconnected: () => { if (voiceClientRef.current) endLiveVoice() },
                onError: (msg) => addMsg('assistant', `\u26A0\uFE0F Voice: ${msg}`),
            })
            voiceClientRef.current = client
            await client.connect()
            setVoiceMode(true)
        } catch (err) {
            voiceClientRef.current = null
            addMsg('assistant', `\u26A0\uFE0F Could not start live voice: ${err.message || err}. Please check mic permission and login.`)
        } finally {
            setLoading(false)
        }
    }

    const handleMicClick = () => (voiceMode ? endLiveVoice() : startLiveVoice())

    // ── v5.0 Sathi chat: WebSocket token streaming, REST fallback ────────────
    const ensureSessionId = () => {
        if (!sessionIdRef.current) {
            sessionIdRef.current = crypto.randomUUID?.()
                || `web-${Date.now()}-${Math.random().toString(16).slice(2)}`
        }
        return sessionIdRef.current
    }

    const openChatSocket = () => new Promise((resolve, reject) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return resolve(wsRef.current)
        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const ws = new WebSocket(`${proto}://${window.location.host}/ws/session/${ensureSessionId()}`)
        const timer = setTimeout(() => { ws.close(); reject(new Error('ws open timeout')) }, 4000)
        ws.onopen = () => { clearTimeout(timer); wsRef.current = ws; resolve(ws) }
        ws.onerror = () => { clearTimeout(timer); reject(new Error('ws error')) }
    })

    const finishAssistantTurn = (data) => {
        const schemes = (data.active_schemes || []).map(sch => ({
            id: sch.schemeCode,
            code: sch.schemeCode,
            name: sch.name,
            benefit: sch.benefitAmount || '',
        }))
        const finalMsg = { role: 'assistant', text: data.reply || 'Samajh gaya!', intent: data.intent, schemes }
        // done.reply is authoritative — replace the streaming bubble (a mid-stream
        // provider fallback on the server can leave stale partial tokens in it)
        setMessages(m => (m[m.length - 1]?.streaming ? [...m.slice(0, -1), finalMsg] : [...m, finalMsg]))
        setAgentSplash(n => n + 1)          // bright splash: an agent just ran
    }

    const sendViaSocket = async (text) => {
        const ws = await openChatSocket()
        return new Promise((resolve, reject) => {
            let streamed = ''
            let settled = false
            const settle = (fn, arg) => { if (!settled) { settled = true; fn(arg) } }
            ws.onmessage = (ev) => {
                let frame
                try { frame = JSON.parse(ev.data) } catch { return }
                if (frame.type === 'token') {
                    streamed += frame.text
                    setLoading(false)       // council bubble out, live bubble in
                    setMessages(m => {
                        const last = m[m.length - 1]
                        return last?.streaming
                            ? [...m.slice(0, -1), { ...last, text: streamed }]
                            : [...m, { role: 'assistant', text: streamed, schemes: [], streaming: true }]
                    })
                } else if (frame.type === 'done') {
                    finishAssistantTurn(frame)
                    settle(resolve)
                } else if (frame.error) {
                    addMsg('assistant', frame.error)
                    settle(resolve)
                }
            }
            ws.onclose = (ev) => {
                if (wsRef.current === ws) wsRef.current = null
                if (settled) return
                if (ev.code === 1008) {
                    addMsg('assistant', 'Your session has expired. Please login again from the Profile tab.')
                    settle(resolve)
                } else if (streamed) {
                    addMsg('assistant', 'Connection dropped mid-reply — please send that again.')
                    settle(resolve)
                } else {
                    settle(reject, new Error('ws closed before reply'))   // caller falls back to REST
                }
            }
            ws.send(JSON.stringify({ message: text, lang, channel: 'web' }))
        })
    }

    const sendViaRest = async (text) => {
        const res = await fetch(`/orchestrator/chat`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, session_id: sessionIdRef.current })
        })
        if (res.ok) {
            const data = await res.json()
            sessionIdRef.current = data.session_id
            finishAssistantTurn(data)
        } else if (res.status === 401) {
            addMsg('assistant', 'Your session has expired. Please login again from the Profile tab.')
        } else {
            addMsg('assistant', 'Could not connect to backend. Browse schemes at /schemes.')
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
            // v5.0: typing always goes through the real orchestrator, whether or
            // not voice mode is active — speaking and typing share one
            // conversation thread now, not a separate voice-only interview.
            // WebSocket streams tokens live; falls back to REST if the socket
            // can't be established (same turn logic server-side either way).
            // Cookie auth; 1008/401 = OTP session expired.
            try {
                await sendViaSocket(text)
            } catch {
                await sendViaRest(text)
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
        if (input.trim()) sendMessage()
    }

    const handleKey = e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleFormSubmit(e)
        }
    }

    return (
        <div className="page-wrapper chat-wrapper">
            {agentSplash > 0 && <div key={agentSplash} className="agent-splash" aria-hidden="true" />}
            <Navbar />

            {voiceMode && (
                <div className="voice-mode-banner">
                    <span className="voice-pulse-dot" />
                    <span>
                        {botSpeaking
                            ? '🔊 Sathi bol raha hai… (bolkar interrupt kar sakte hain)'
                            : userSpeaking
                                ? '🎙️ Sun raha hoon…'
                                : '🔴 Live — boliye, Sathi sun raha hai'}
                    </span>
                    <button className="btn btn-ghost btn-sm" onClick={endLiveVoice}>
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
                    <BubbleIn key={i} className={`chat-bubble-row ${msg.role}`} fromUser={msg.role === 'user'}>
                        {msg.role === 'assistant' && (
                            <div className="chat-avatar sathi-avatar-custom"><SathiAvatar /></div>
                        )}
                        <div className={`chat-bubble glass-card ${msg.role}`}>
                            {msg.voice && <span className="chat-voice-tag">🔊 Voice</span>}
                            <p className="chat-text" style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</p>
                            {msg.schemes && msg.schemes.length > 0 && (
                                <div className="chat-schemes">
                                    {msg.schemes.map(s => (
                                        <div key={s.id || s.name} className="chat-scheme-card">
                                            <div onClick={() => navigate(`/schemes/${s.id || 'scheme'}`, { state: s })} style={{ cursor: 'pointer' }}>
                                                <p className="scheme-card-title">{s.name}</p>
                                                <p className="scheme-card-benefit">{s.benefit}</p>
                                            </div>
                                            {s.code && (
                                                <button className="btn btn-saffron-outline btn-sm" style={{ marginTop: 6 }}
                                                        onClick={(e) => { e.stopPropagation(); saveScheme(s) }}>
                                                    Save to My Applications
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                            {msg.intent && (
                                <p className="text-subtle" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.6, marginTop: 6 }}>
                                    {msg.intent.replace(/_/g, ' ')}
                                </p>
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
                    </BubbleIn>
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
                            <AgentCouncil working />
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
                    className={`chat-mic-btn ${userSpeaking ? 'recording' : voiceMode ? 'active' : ''}`}
                    onClick={handleMicClick}
                    title={voiceMode ? 'End live voice call' : 'Start live voice call'}
                    disabled={loading}
                >
                    {voiceMode ? <MicOff size={18} /> : <Mic size={18} />}
                </button>

                <textarea
                    className="chat-input"
                    placeholder={voiceMode ? '🔴 Live call — you can also type here' : t('chat.placeholder')}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    rows={1}
                />
                <button
                    type="submit"
                    className="chat-send-btn btn btn-primary btn-sm"
                    disabled={loading || !input.trim()}
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
