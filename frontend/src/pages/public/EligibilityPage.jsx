import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
    Send, Loader2, MessageCircle, PanelRightOpen, PanelLeftOpen,
    CheckCircle2, XCircle, HelpCircle, Lock, ArrowRight, Mic, Square, Volume2,
} from 'lucide-react'
import { PublicPage } from '../../components/PublicShell'
import LoginPrompt from '../../components/LoginPrompt'
import { isGuest } from '../../lib/auth'
import { ai } from '../../lib/api'
import { formatInr } from '../../lib/emiCalculator'
import { useLang, useAutoTranslate } from '../../lib/i18n'
import './PublicPages.css'

/**
 * Conversational eligibility intake — replaces the earlier plain form.
 *
 * Why: a static "here are 6 schemes, read their criteria" catalogue is
 * exactly what nsfdc.nic.in and myscheme.gov.in already are, and they're the
 * authoritative source — a directory can't out-compete a directory. The one
 * thing an AI layer can actually offer a citizen who doesn't know the term
 * "unit-cost ceiling" is: describe your situation in plain language, and
 * have THAT translated into the real eligibility check for you.
 *
 * The chat never answers "you qualify" itself — see
 * ai_service/services/eligibility_assistant.py's docstring. It only extracts
 * structured facts (need/estimatedCost/annualIncome/category/gender) from
 * what the citizen says, then calls the same real
 * POST /api/v2/sih/credit/eligibility this page always called. `results` in
 * the response IS that endpoint's real response, rendered here exactly as
 * the old form's result cards did — nothing here is chat-generated prose
 * standing in for a verdict.
 *
 * Session-backed, not stateless: the server keys each turn to a session id
 * under an anonymous `guest:` identity so the orchestrator can carry
 * conversation history. `context` is still echoed back and forth for
 * backward compatibility with the pre-orchestrator client, but the session
 * document is the source of truth. UI.privacy says exactly this — see the
 * comment there.
 */
const UI = {
    title: 'Check your eligibility',
    sub: "Tell Sathi about your situation in your own words — no forms, no scheme names to know in advance.",
    // Says exactly what the backend does, no more. This used to read
    // "Nothing is saved unless you create an account and ask us to", which
    // stopped being true when the flow moved onto the orchestrator and
    // started persisting turns to conversation_sessions under an anonymous
    // guest id. A privacy promise the code doesn't keep is worse than a
    // narrower one it does.
    privacy: 'Your answers are used only to work out which schemes you qualify for. This conversation is saved against a random session number so Sathi can remember what you have already told it — not against your name, and no account is created.',
    inputPh: 'Type your answer…',
    send: 'Send',
    thinking: 'Sathi is typing…',
    resultsTitle: 'Your indicative results',
    resultsPanelTitle: 'Results',
    indicative: 'Indicative only — the lending branch makes the final decision.',
    eligible: 'You appear to qualify',
    notEligible: 'You do not appear to qualify',
    unknown: 'We need a little more information',
    needMore: 'To give you a clear answer, we still need:',
    youCanBorrow: 'You could borrow up to',
    marginMoney: 'Your own contribution (margin money)',
    monthlyEmi: 'Indicative monthly EMI',
    whyNot: 'Why not',
    rate: 'Interest rate',
    costCapped: 'Your project costs more than this scheme funds, so the figures above are capped at the scheme maximum.',
    viewScheme: 'View scheme',
    applyNow: 'Apply for this scheme',
    saveResults: 'Save these results',
    loginToApply: 'apply for this scheme',
    loginToSave: 'save your results',
    loginSaveBody: 'Create an account to keep these results, come back to them later, and apply when you are ready.',
    error: "Couldn't reach Sathi right now. Please try again in a moment.",
    noMatch: 'No scheme matched your answers so far. You can still browse all schemes, or keep chatting to add more detail.',
    browseAll: 'Browse all schemes',
    showResults: 'Show results', showChat: 'Continue chatting',
    startOver: 'Start over',
    micStart: 'Speak your answer',
    micStop: 'Stop and send',
    listening: 'Listening…',
    transcribing: 'Sathi is listening back…',
    micDenied: "Couldn't access your microphone. Check your browser's permission for this site, or type instead.",
    micUnsupported: 'Voice input is not supported in this browser — please type instead.',
    voiceError: "Couldn't process that recording. Please try again, or type instead.",
}
const MISSING_LABELS = {
    estimatedCost: 'how much your project or course will cost',
    annualIncome: 'your annual family income',
    category: 'your social category',
    gender: 'whether the applicant is a woman (some schemes are women-only)',
}

function ResultsPanel({ result, tr, onApply, onSave }) {
    const verdictUi = {
        eligible: { icon: <CheckCircle2 size={16} />, cls: 'gov-notice-ok', text: UI.eligible },
        not_eligible: { icon: <XCircle size={16} />, cls: 'gov-notice-error', text: UI.notEligible },
        insufficient_data: { icon: <HelpCircle size={16} />, cls: 'gov-notice-warn', text: UI.unknown },
    }[result?.verdict]

    return (
        <div>
            <h2 className="gov-section-title" style={{ marginTop: 0 }}>{tr(UI.resultsTitle)}</h2>
            <p className="gov-section-sub">{tr(UI.indicative)}</p>

            {verdictUi && (
                <div className={`gov-notice ${verdictUi.cls}`} style={{ marginBottom: 16 }}>
                    {verdictUi.icon}
                    <span>
                        <strong>{tr(verdictUi.text)}</strong>
                        {result.note && <><br />{tr(result.note)}</>}
                    </span>
                </div>
            )}

            {result.missingProfileData?.length > 0 && (
                <div className="gov-card" style={{ marginBottom: 16 }}>
                    <p style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>{tr(UI.needMore)}</p>
                    <ul className="gov-reason" style={{ paddingLeft: 18, margin: 0 }}>
                        {[...new Set(result.missingProfileData)].map((f) => (
                            <li key={f}>{tr(MISSING_LABELS[f] || f)}</li>
                        ))}
                    </ul>
                </div>
            )}

            {(result.recommendations || []).length === 0 && (
                <div className="gov-empty">
                    <p style={{ marginBottom: 14 }}>{tr(UI.noMatch)}</p>
                    <Link to="/credit-schemes" className="gov-btn gov-btn-secondary gov-btn-sm">{tr(UI.browseAll)}</Link>
                </div>
            )}

            {(result.recommendations || []).map((rec) => (
                <div
                    key={rec.productId}
                    className={`gov-card gov-result ${rec.eligible ? 'eligible' : (rec.missingProfileData?.length ? 'unknown' : 'not-eligible')}`}
                    style={{ marginBottom: 14 }}
                >
                    <span className="gov-scheme-code">{rec.code}</span>
                    <h3 style={{ fontSize: 17, marginBottom: 10 }}>{tr(rec.name)}</h3>

                    {rec.eligible && (
                        <div className="gov-facts" style={{ marginBottom: 10 }}>
                            <div>
                                <div className="gov-fact-label">{tr(UI.youCanBorrow)}</div>
                                <div className="gov-fact-value">{formatInr(rec.eligibleLoanAmount ?? rec.maxLoanAmount)}</div>
                            </div>
                            <div>
                                <div className="gov-fact-label">{tr(UI.marginMoney)}</div>
                                <div className="gov-fact-value">{formatInr(rec.marginMoney ?? 0)}</div>
                            </div>
                            {rec.indicativeEmi?.emi > 0 && (
                                <div>
                                    <div className="gov-fact-label">{tr(UI.monthlyEmi)}</div>
                                    <div className="gov-fact-value">{formatInr(rec.indicativeEmi.emi)}</div>
                                </div>
                            )}
                            <div>
                                <div className="gov-fact-label">{tr(UI.rate)}</div>
                                <div className="gov-fact-value">{rec.interestRate}%</div>
                            </div>
                        </div>
                    )}

                    {rec.costExceedsCap && (
                        <div className="gov-notice gov-notice-warn" style={{ marginBottom: 10 }}>
                            <HelpCircle size={15} /> <span>{tr(UI.costCapped)}</span>
                        </div>
                    )}

                    {rec.failed?.length > 0 && (
                        <ul className="gov-reason" style={{ paddingLeft: 18, marginTop: 0, marginBottom: 10 }}>
                            <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{tr(UI.whyNot)}</p>
                            {rec.failed.map((f, i) => <li key={i}>{tr(f)}</li>)}
                        </ul>
                    )}
                    {rec.eligible && rec.matched?.length > 0 && (
                        <ul className="gov-reason" style={{ paddingLeft: 18, marginTop: 0, marginBottom: 10 }}>
                            {rec.matched.slice(0, 3).map((m, i) => <li key={i}>{tr(m)}</li>)}
                        </ul>
                    )}

                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <Link to={`/credit-schemes/${rec.productId}`} className="gov-btn gov-btn-ghost gov-btn-sm">
                            {tr(UI.viewScheme)}
                        </Link>
                        {rec.eligible && (
                            <button className="gov-btn gov-btn-primary gov-btn-sm" onClick={() => onApply(rec)}>
                                {tr(UI.applyNow)} <ArrowRight size={14} />
                            </button>
                        )}
                    </div>
                </div>
            ))}

            {(result.recommendations || []).length > 0 && (
                <button className="gov-btn gov-btn-secondary gov-btn-sm" onClick={onSave}>
                    {tr(UI.saveResults)}
                </button>
            )}
        </div>
    )
}

export default function EligibilityPage() {
    const navigate = useNavigate()
    const { lang } = useLang()
    const [messages, setMessages] = useState([]) // [{role, text}]
    const [context, setContext] = useState({})
    const [result, setResult] = useState(null)
    const [input, setInput] = useState('')
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState('')
    const [prompt, setPrompt] = useState(null)
    // Mobile/narrow layout only has room for one panel at a time — this
    // controls which. Desktop shows both side by side regardless.
    const [mobileView, setMobileView] = useState('chat') // 'chat' | 'results'
    // idle | recording | processing — processing covers both the upload and
    // waiting for Sathi's spoken reply, same as `busy` does for text.
    const [voiceState, setVoiceState] = useState('idle')
    const [voiceError, setVoiceError] = useState('')
    const bottomRef = useRef(null)
    const started = useRef(false)
    const mediaRecorderRef = useRef(null)
    const audioChunksRef = useRef([])
    const audioPlayerRef = useRef(null)

    const tr = useAutoTranslate([
        ...Object.values(UI),
        ...Object.values(MISSING_LABELS),
        ...messages.map((m) => m.text),
        ...(result?.recommendations || []).flatMap((r) => [r.name, ...(r.matched || []), ...(r.failed || [])]),
        result?.note,
    ].filter(Boolean))

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, busy])

    // Sathi opens the conversation rather than waiting on the citizen to
    // guess what to type first — an empty landing chat is as intimidating
    // as an empty form.
    useEffect(() => {
        if (started.current) return
        started.current = true
        send('', true)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const send = async (text, silent = false) => {
        if (!silent && !text.trim()) return
        if (!silent) setMessages((m) => [...m, { role: 'user', text }])
        setInput(''); setBusy(true); setError('')
        try {
            const res = await ai.eligibilityChat(text, context, lang)
            setContext(res.context)
            setMessages((m) => [...m, { role: 'assistant', text: res.bot_reply }])
            if (res.results) {
                setResult(res.results)
                setMobileView('results')
            }
        } catch (err) {
            setError(err.message || tr(UI.error))
        } finally {
            setBusy(false)
        }
    }

    // ── Voice: MediaRecorder captures mic audio; the whole clip goes to
    // /eligibility-assistant/voice as one turn (Sarvam STT -> the same
    // EligibilityAssistant text uses -> Sarvam TTS). Tap-to-start,
    // tap-to-stop rather than press-and-hold — more reliable on mobile,
    // where a hold gesture competes with scrolling.
    const startRecording = async () => {
        setVoiceError('')
        if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
            setVoiceError(tr(UI.micUnsupported))
            return
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
                .find((t) => MediaRecorder.isTypeSupported?.(t))
            const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
            audioChunksRef.current = []
            recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
            recorder.onstop = () => {
                stream.getTracks().forEach((t) => t.stop())
                const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' })
                sendVoice(blob)
            }
            mediaRecorderRef.current = recorder
            recorder.start()
            setVoiceState('recording')
        } catch {
            setVoiceError(tr(UI.micDenied))
        }
    }

    const stopRecording = () => {
        mediaRecorderRef.current?.stop()
        setVoiceState('processing')
    }

    const sendVoice = async (blob) => {
        setBusy(true); setError('')
        try {
            const res = await ai.eligibilityVoice(blob, context, lang)
            if (res.transcript) setMessages((m) => [...m, { role: 'user', text: res.transcript }])
            setContext(res.context)
            setMessages((m) => [...m, { role: 'assistant', text: res.bot_reply }])
            if (res.results) {
                setResult(res.results)
                setMobileView('results')
            }
            if (res.audio_base64 && audioPlayerRef.current) {
                audioPlayerRef.current.src = `data:audio/mpeg;base64,${res.audio_base64}`
                audioPlayerRef.current.play().catch(() => {}) // autoplay can be blocked — silent, the reply is still shown as text
            }
        } catch (err) {
            setVoiceError(err.message || tr(UI.voiceError))
        } finally {
            setBusy(false)
            setVoiceState('idle')
        }
    }

    const onApply = (rec) => {
        if (isGuest()) { setPrompt({ action: tr(UI.loginToApply), body: tr(UI.loginSaveBody) }); return }
        const s = context.slots || {}
        navigate(`/apply/${rec.productId}`, {
            state: {
                productId: rec.productId, schemeCode: rec.code,
                estimatedCost: s.estimatedCost, annualIncome: s.annualIncome,
                category: s.category, gender: s.gender, need: s.need,
            },
        })
    }
    const onSave = () => {
        if (isGuest()) { setPrompt({ action: tr(UI.loginToSave), body: tr(UI.loginSaveBody) }); return }
        navigate('/home')
    }

    const chatPanel = (
        <div className="gov-chat-panel">
            <div className="gov-chat-messages">
                {messages.map((m, i) => (
                    <div key={i} className={`gov-chat-bubble ${m.role}`}>{tr(m.text)}</div>
                ))}
                {voiceState === 'recording' && (
                    <div className="gov-chat-bubble user gov-chat-typing"><Volume2 size={13} style={{ verticalAlign: '-2px' }} /> {tr(UI.listening)}</div>
                )}
                {voiceState === 'processing' && (
                    <div className="gov-chat-bubble assistant gov-chat-typing">{tr(UI.transcribing)}</div>
                )}
                {busy && voiceState === 'idle' && <div className="gov-chat-bubble assistant gov-chat-typing">{tr(UI.thinking)}</div>}
                {error && <div className="gov-notice gov-notice-error" style={{ margin: '8px 0' }}>{error}</div>}
                {voiceError && <div className="gov-notice gov-notice-error" style={{ margin: '8px 0' }}>{voiceError}</div>}
                <div ref={bottomRef} />
            </div>
            {/* Hidden player for Sathi's spoken reply — src is set to a data:
                URL per turn in sendVoice(), not rendered with controls; the
                reply is always shown as text too, so autoplay being blocked
                by the browser never loses information, just the audio. */}
            <audio ref={audioPlayerRef} hidden />
            <form
                className="gov-chat-inputrow"
                onSubmit={(e) => { e.preventDefault(); send(input) }}
            >
                <input
                    className="gov-input"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={tr(UI.inputPh)}
                    disabled={busy || voiceState !== 'idle'}
                    autoFocus
                />
                <button
                    type="button"
                    className={`gov-btn gov-btn-sm ${voiceState === 'recording' ? 'gov-mic-recording' : 'gov-btn-ghost'}`}
                    onClick={voiceState === 'recording' ? stopRecording : startRecording}
                    disabled={busy && voiceState === 'idle'}
                    title={tr(voiceState === 'recording' ? UI.micStop : UI.micStart)}
                    aria-label={tr(voiceState === 'recording' ? UI.micStop : UI.micStart)}
                >
                    {voiceState === 'recording' ? <Square size={15} /> : <Mic size={15} />}
                </button>
                <button className="gov-btn gov-btn-primary gov-btn-sm" type="submit" disabled={busy || !input.trim() || voiceState !== 'idle'}>
                    {busy && voiceState === 'idle' ? <Loader2 size={15} className="spin" /> : <Send size={15} />}
                </button>
            </form>
            <p className="gov-hint" style={{ marginTop: 10 }}>
                <Lock size={12} style={{ verticalAlign: '-2px' }} /> {tr(UI.privacy)}
            </p>
        </div>
    )

    const resultsPanel = result && (
        <ResultsPanel result={result} tr={tr} onApply={onApply} onSave={onSave} />
    )

    return (
        <PublicPage tr={tr}>
            <section className="gov-hero" style={{ paddingBottom: 20 }}>
                <div className="gov-container">
                    <h1>{tr(UI.title)}</h1>
                    <p className="gov-hero-sub">{tr(UI.sub)}</p>
                </div>
            </section>

            <section className="gov-section" style={{ paddingTop: 0 }}>
                <div className="gov-container">
                    {/* Mobile: one panel at a time with a toggle, once results exist.
                        Desktop: both panels side by side always — the CSS grid does
                        this, .gov-eligibility-mobile-tabs is hidden there. */}
                    {result && (
                        <div className="gov-eligibility-mobile-tabs">
                            <button
                                className={`gov-btn gov-btn-sm ${mobileView === 'chat' ? 'gov-btn-primary' : 'gov-btn-ghost'}`}
                                onClick={() => setMobileView('chat')}
                            >
                                <MessageCircle size={14} /> {tr(UI.showChat)}
                            </button>
                            <button
                                className={`gov-btn gov-btn-sm ${mobileView === 'results' ? 'gov-btn-primary' : 'gov-btn-ghost'}`}
                                onClick={() => setMobileView('results')}
                            >
                                {mobileView === 'results' ? <PanelLeftOpen size={14} /> : <PanelRightOpen size={14} />} {tr(UI.showResults)}
                            </button>
                        </div>
                    )}

                    <div className={`gov-eligibility-layout ${result ? 'has-results' : ''}`}>
                        <div className={`gov-eligibility-chat-col ${mobileView === 'results' ? 'mobile-hidden' : ''}`}>
                            {chatPanel}
                        </div>
                        {result && (
                            <div className={`gov-eligibility-results-col ${mobileView === 'chat' ? 'mobile-hidden' : ''}`}>
                                {resultsPanel}
                            </div>
                        )}
                    </div>
                </div>
            </section>

            <LoginPrompt open={!!prompt} onClose={() => setPrompt(null)} action={prompt?.action}>
                {prompt?.body}
            </LoginPrompt>
        </PublicPage>
    )
}
