import { useEffect, useState } from 'react'
import { CheckCircle, Clock, Circle, RefreshCw, MessageSquareWarning, FileText } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import { Reveal } from '../components/motion'
import { Sparkles } from 'lucide-react'
import { gateway, ai } from '../lib/api'
import '../components/components.css'
import './StatusPage.css'

// v5.0: real applications from the gateway (saved via Sathi chat), with the
// same glass timeline visuals the demo version had. No more hardcoded data.

const STAGES = ['saved', 'in_progress', 'submitted', 'approved', 'disbursed']
const STAGE_LABEL = {
    saved: 'Saved', in_progress: 'In Progress', submitted: 'Submitted',
    approved: 'Approved', disbursed: 'Disbursed', rejected: 'Rejected',
}

function Timeline({ status }) {
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
                            <p className="timeline-title">{STAGE_LABEL[stage]}</p>
                            <p className="timeline-sub">{done ? 'Completed ✓' : isPending ? 'Next step' : 'Upcoming'}</p>
                        </div>
                    </div>
                )
            })}
        </div>
    )
}

export default function StatusPage() {
    const [apps, setApps] = useState(null)
    const [note, setNote] = useState('')
    const [grievanceFor, setGrievanceFor] = useState(null)
    const [complaint, setComplaint] = useState('')

    const load = async () => {
        try {
            setApps(await gateway.listApplications())
            setNote('')
        } catch (err) {
            setApps([])
            setNote(err.status === 401 || err.status === 403
                ? 'Please login to see your applications.'
                : `Could not load applications: ${err.message}`)
        }
    }
    useEffect(() => { load() }, [])

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
        } catch (err) { setNote(err.message) }
    }

    return (
        <div className="page-wrapper">
            <Navbar />
            <main className="page-content">

                <div className="status-header">
                    <div>
                        <div className="sathi-tag" style={{ position: 'static', display: 'inline-flex', marginBottom: 8 }}><Sparkles size={10} /> Application Tracker</div>
                        <h1 className="status-title font-display">My Applications</h1>
                    </div>
                    <button className="btn btn-ghost btn-sm" onClick={load}>
                        <RefreshCw size={14} /> Refresh
                    </button>
                </div>

                {note && (
                    <div className="glass-card" style={{ padding: 14, marginBottom: 14, whiteSpace: 'pre-wrap', fontSize: 13.5 }}>
                        {note}
                    </div>
                )}

                {apps === null && (
                    <div className="glass-card" style={{ padding: 20, textAlign: 'center' }}>
                        <p className="text-muted">Loading your applications…</p>
                    </div>
                )}

                {apps?.length === 0 && !note && (
                    <div className="glass-card" style={{ padding: 24, textAlign: 'center' }}>
                        <FileText size={28} className="text-saffron" />
                        <p className="text-muted" style={{ marginTop: 10 }}>
                            No applications yet. Ask Sathi about schemes — every scheme it suggests
                            has a "Save to My Applications" button.
                        </p>
                    </div>
                )}

                {apps?.map((app) => (
                    <Reveal key={app.id}>
                    <div className="glass-card glass-card-glow status-active-card" style={{ marginBottom: 16 }}>
                        <div className="status-active-header">
                            <div>
                                <div className={`badge badge-${app.status === 'rejected' ? 'red' : app.status === 'approved' || app.status === 'disbursed' ? 'green' : 'saffron'}`} style={{ marginBottom: 8 }}>
                                    {STAGE_LABEL[app.status] || app.status}
                                </div>
                                <h2 className="status-scheme-name">{app.schemeName}</h2>
                                <p className="text-muted" style={{ fontSize: 12 }}>
                                    {app.schemeCode}{app.externalAppId ? ` · Ref: ${app.externalAppId}` : ''}
                                </p>
                            </div>
                        </div>

                        {app.status !== 'rejected' && <Timeline status={app.status} />}

                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
                            {app.status === 'saved' && (
                                <button className="btn btn-saffron-outline btn-sm" onClick={() => advance(app, 'in_progress')}>
                                    I started applying
                                </button>
                            )}
                            {app.status === 'in_progress' && (
                                <button className="btn btn-saffron-outline btn-sm" onClick={() => advance(app, 'submitted')}>
                                    I submitted it
                                </button>
                            )}
                            <button className="btn btn-ghost btn-sm" onClick={() => { setGrievanceFor(app); setNote('') }}>
                                <MessageSquareWarning size={14} /> File grievance
                            </button>
                        </div>

                        {grievanceFor?.id === app.id && (
                            <form onSubmit={fileGrievance} style={{ marginTop: 12 }}>
                                <textarea className="input-glass" rows={3} value={complaint} required
                                          placeholder="Describe the problem — e.g. installment not received for 3 months, bank details are correct…"
                                          onChange={e => setComplaint(e.target.value)} style={{ width: '100%' }} />
                                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                                    <button className="btn btn-primary btn-sm btn-aarti" disabled={!complaint.trim()}>Submit grievance</button>
                                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setGrievanceFor(null)}>Cancel</button>
                                </div>
                            </form>
                        )}
                    </div>
                    </Reveal>
                ))}

            </main>
            <BottomNav />
        </div>
    )
}
