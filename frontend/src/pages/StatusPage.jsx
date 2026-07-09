import { useEffect, useState } from 'react'
import { CheckCircle, Clock, Circle, RefreshCw, MessageSquareWarning, FileText } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { Reveal } from '../components/motion'
import { Sparkles } from 'lucide-react'
import { gateway, ai } from '../lib/api'
import { useAutoTranslate } from '../lib/i18n'
import '../components/components.css'
import './StatusPage.css'

// v5.0: real applications from the gateway (saved via Sathi chat), with the
// same glass timeline visuals the demo version had. No more hardcoded data.

const STAGES = ['saved', 'in_progress', 'submitted', 'approved', 'disbursed']
const STAGE_LABEL = {
    saved: 'Saved', in_progress: 'In Progress', submitted: 'Submitted',
    approved: 'Approved', disbursed: 'Disbursed', rejected: 'Rejected',
}
const UI = {
    tracker: 'Application Tracker', myApps: 'My Applications', refresh: 'Refresh',
    loading: 'Loading your applications…',
    empty: 'No applications yet. Ask Sathi about schemes — every scheme it suggests has a "Save to My Applications" button.',
    started: 'I started applying', submitted: 'I submitted it', fileGrievance: 'File grievance',
    grievancePh: 'Describe the problem — e.g. installment not received for 3 months, bank details are correct…',
    submitGrievance: 'Submit grievance', cancel: 'Cancel',
    done: 'Completed ✓', nextStep: 'Next step', upcoming: 'Upcoming',
    myGrievances: 'My Grievances',
    grievancesEmpty: 'No grievances filed yet. If a scheme benefit is stuck, use "File grievance" on the application above.',
    addRef: 'I filed it on CPGRAMS — add my reference number',
    refPh: 'CPGRAMS registration number, e.g. DOCPG/E/2026/0012345',
    saveRef: 'Save reference', cpgramsHint: 'After you file on pgportal.gov.in, save the registration number here to track it.',
}
const GRIEVANCE_LABEL = {
    recorded: 'Recorded', filed_on_portal: 'Filed on CPGRAMS', resolved: 'Resolved',
}
const ALL_STATIC = [...Object.values(UI), ...Object.values(STAGE_LABEL), ...Object.values(GRIEVANCE_LABEL)]

function Timeline({ status, tr }) {
    const idx = STAGES.indexOf(status)
    return (
        <div className="timeline" style={{ marginTop: 16 }}>
            {STAGES.map((stage, i) => {
                const done = i <= idx
                const isPending = i === idx + 1
                const Icon = done ? CheckCircle : isPending ? Clock : Circle
                return (
                    <div key={stage} className={`timeline-item ${done ? 'done' : ''}`}>
                        <div className={`timeline-dot ${done ? 'done' : isPending ? 'pending' : 'future'}`}>
                            <Icon size={14} />
                        </div>
                        <div className="timeline-content">
                            <p className="timeline-title">{tr(STAGE_LABEL[stage])}</p>
                            <p className="timeline-sub">{tr(done ? UI.done : isPending ? UI.nextStep : UI.upcoming)}</p>
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

export default function StatusPage() {
    const [apps, setApps] = useState(null)
    const [grievances, setGrievances] = useState([])
    const [note, setNote] = useState('')
    const [grievanceFor, setGrievanceFor] = useState(null)
    const [complaint, setComplaint] = useState('')
    const [refFor, setRefFor] = useState(null)      // grievance_id currently adding a CPGRAMS ref
    const [refValue, setRefValue] = useState('')
    // Static labels + the live scheme names on each application/grievance card
    const tr = useAutoTranslate([...ALL_STATIC,
        ...(apps || []).map(a => a.schemeName).filter(Boolean),
        ...grievances.map(g => g.schemeName).filter(Boolean)])

    const loadGrievances = async () => {
        try { setGrievances((await ai.listGrievances())?.grievances || []) }
        catch { /* grievances are secondary — never block the applications view */ }
    }

    const load = async () => {
        try {
            setApps(await gateway.listApplications())
            setNote('')
            loadGrievances()
        } catch (err) {
            setApps([])
            setNote(err.status === 401 || err.status === 403
                ? 'Please login to see your applications.'
                : `Could not load applications: ${err.message}`)
        }
    }
    useEffect(() => { load() }, [])

    const saveCpgramsRef = async (e) => {
        e.preventDefault()
        try {
            await ai.setCpgramsRef(refFor, refValue.trim())
            setRefFor(null); setRefValue('')
            loadGrievances()
        } catch (err) { setNote(err.message) }
    }

    const advance = async (app, status) => {
        try { await gateway.updateApplication(app.id, { status }); load() }
        catch (err) { setNote(err.message) }
    }

    const fileGrievance = async (e) => {
        e.preventDefault()
        try {
            const res = await ai.fileGrievance({
                complaint_description: complaint,
                scheme_code: grievanceFor.schemeCode,
                external_app_id: grievanceFor.externalAppId || null,
            })
            setNote(res.reply)
            setGrievanceFor(null); setComplaint('')
            loadGrievances()   // show the newly-filed grievance in the tracking list below
        } catch (err) { setNote(err.message) }
    }

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="status-header">
                    <div>
                        <div className="sathi-tag" style={{ position: 'static', display: 'inline-flex', marginBottom: 8 }}><Sparkles size={10} /> {tr(UI.tracker)}</div>
                        <h1 className="status-title font-display">{tr(UI.myApps)}</h1>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={load}>
                        <RefreshCw size={14} /> {tr(UI.refresh)}
                    </button>
                </div>

                {note && (
                    <div className="glass-card" style={{ padding: 14, marginBottom: 14, whiteSpace: 'pre-wrap', fontSize: 13.5 }}>
                        {tr(note)}
                    </div>
                )}

                {apps === null && (
                    <div className="glass-card" style={{ padding: 20, textAlign: 'center' }}>
                        <p className="text-muted">{tr(UI.loading)}</p>
                    </div>
                )}

                {apps?.length === 0 && !note && (
                    <div className="glass-card" style={{ padding: 24, textAlign: 'center' }}>
                        <FileText size={28} className="text-saffron" />
                        <p className="text-muted" style={{ marginTop: 10 }}>
                            {tr(UI.empty)}
                        </p>
                    </div>
                )}

                {apps?.map((app) => (
                    <Reveal key={app.id}>
                    <div className="glass-card glass-card-glow status-active-card" style={{ marginBottom: 16 }}>
                        <div className="status-active-header">
                            <div>
                                <div className={`badge badge-${app.status === 'rejected' ? 'red' : app.status === 'approved' || app.status === 'disbursed' ? 'green' : 'saffron'}`} style={{ marginBottom: 8 }}>
                                    {tr(STAGE_LABEL[app.status] || app.status)}
                                </div>
                                <h2 className="status-scheme-name">{tr(app.schemeName)}</h2>
                                <p className="text-muted" style={{ fontSize: 12 }}>
                                    {app.schemeCode}{app.externalAppId ? ` · Ref: ${app.externalAppId}` : ''}
                                </p>
                            </div>
                        </div>

                        {app.status !== 'rejected' && <Timeline status={app.status} tr={tr} />}

                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
                            {app.status === 'saved' && (
                                <button className="btn btn-saffron-outline btn-sm" onClick={() => advance(app, 'in_progress')}>
                                    {tr(UI.started)}
                                </button>
                            )}
                            {app.status === 'in_progress' && (
                                <button className="btn btn-saffron-outline btn-sm" onClick={() => advance(app, 'submitted')}>
                                    {tr(UI.submitted)}
                                </button>
                            )}
                            <button className="btn btn-ghost btn-sm" onClick={() => { setGrievanceFor(app); setNote('') }}>
                                <MessageSquareWarning size={14} /> {tr(UI.fileGrievance)}
                            </button>
                        </div>

                        {grievanceFor?.id === app.id && (
                            <form onSubmit={fileGrievance} style={{ marginTop: 12 }}>
                                <textarea className="input-glass" rows={3} value={complaint} required
                                          placeholder={tr(UI.grievancePh)}
                                          onChange={e => setComplaint(e.target.value)} style={{ width: '100%' }} />
                                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                                    <button className="btn btn-primary btn-sm btn-aarti" disabled={!complaint.trim()}>{tr(UI.submitGrievance)}</button>
                                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setGrievanceFor(null)}>{tr(UI.cancel)}</button>
                                </div>
                            </form>
                        )}
                    </div>
                    </Reveal>
                ))}

                {/* Agent 5 — grievance tracking loop. Shows the citizen's filed
                    grievances; a "recorded" one can capture the CPGRAMS reference
                    number after they self-file on pgportal (-> filed_on_portal). */}
                {grievances.length > 0 && (
                    <div style={{ marginTop: 28 }}>
                        <h2 className="status-title font-display" style={{ fontSize: 22, marginBottom: 14 }}>
                            <MessageSquareWarning size={18} className="text-saffron" style={{ verticalAlign: -3, marginRight: 6 }} />
                            {tr(UI.myGrievances)}
                        </h2>
                        {grievances.map((g) => (
                            <Reveal key={g.grievance_id}>
                            <div className="glass-card" style={{ marginBottom: 12, padding: 16 }}>
                                <div className={`badge badge-${g.status === 'resolved' ? 'green' : g.status === 'filed_on_portal' ? 'saffron' : 'red'}`} style={{ marginBottom: 8 }}>
                                    {tr(GRIEVANCE_LABEL[g.status] || g.status)}
                                </div>
                                {g.schemeName && <h3 className="status-scheme-name" style={{ fontSize: 16 }}>{tr(g.schemeName)}</h3>}
                                <p className="text-muted" style={{ fontSize: 13, marginTop: 4, whiteSpace: 'pre-wrap' }}>{g.complaint}</p>
                                {g.cpgramsRef && (
                                    <p className="text-muted" style={{ fontSize: 12, marginTop: 6 }}>CPGRAMS Ref: <strong>{g.cpgramsRef}</strong></p>
                                )}

                                {g.status === 'recorded' && refFor !== g.grievance_id && (
                                    <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }}
                                            onClick={() => { setRefFor(g.grievance_id); setRefValue('') }}>
                                        <FileText size={14} /> {tr(UI.addRef)}
                                    </button>
                                )}
                                {refFor === g.grievance_id && (
                                    <form onSubmit={saveCpgramsRef} style={{ marginTop: 10 }}>
                                        <p className="text-muted" style={{ fontSize: 12, marginBottom: 6 }}>{tr(UI.cpgramsHint)}</p>
                                        <input className="input-glass" value={refValue} required
                                               placeholder={tr(UI.refPh)}
                                               onChange={e => setRefValue(e.target.value)} style={{ width: '100%' }} />
                                        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                                            <button className="btn btn-primary btn-sm btn-aarti" disabled={!refValue.trim()}>{tr(UI.saveRef)}</button>
                                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRefFor(null)}>{tr(UI.cancel)}</button>
                                        </div>
                                    </form>
                                )}
                            </div>
                            </Reveal>
                        ))}
                    </div>
                )}

            </main>
            <BottomNav />
        </div>
    )
}
