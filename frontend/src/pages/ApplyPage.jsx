import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, Construction } from 'lucide-react'
import { Navbar, BottomNav } from '../components/Navbar'
import '../components/components.css'

// Stub landing page for the credit application form. The application
// assistant chat flow (services/application_assistant.py) already produces
// a real payload shaped exactly like CreditApplicationController.create()'s
// body — {schemeCode, productId, estimatedCost, annualIncome, category,
// tenureMonths, moratoriumMode, verificationMode} — and hands off to this
// route via location.state. The real form (reading these fields to
// pre-fill itself, then calling gateway.createApplication or an equivalent
// POST /api/v2/sih/applications) is a separate, not-yet-built page; this
// stub exists so the chat CTA has somewhere real to land in the meantime,
// and so the payload shape is visible/verifiable end-to-end today.
export default function ApplyPage() {
    const { schemeId } = useParams()
    const { state } = useLocation()
    const navigate = useNavigate()
    const payload = state || null

    return (
        <div className="page-wrapper">
            <Navbar />
            <div className="page-content" style={{ maxWidth: 480, margin: '0 auto', padding: '24px 16px' }}>
                <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>
                    <ArrowLeft size={16} /> Back
                </button>

                <div className="glass-card" style={{ padding: 24, textAlign: 'center' }}>
                    <Construction size={32} className="text-saffron" style={{ marginBottom: 12 }} />
                    <h2 style={{ marginBottom: 8 }}>Application form coming soon</h2>
                    <p className="text-subtle" style={{ marginBottom: 16 }}>
                        Scheme: <strong>{schemeId}</strong>
                    </p>

                    {payload ? (
                        <div style={{ textAlign: 'left', fontSize: 13 }}>
                            <p className="text-subtle" style={{ marginBottom: 8 }}>
                                Sathi already collected these details for you:
                            </p>
                            <pre className="glass-card" style={{ padding: 12, overflowX: 'auto' }}>
                                {JSON.stringify(payload, null, 2)}
                            </pre>
                        </div>
                    ) : (
                        <p className="text-subtle">
                            No pre-filled details found — you got here directly rather than via the chat assistant.
                        </p>
                    )}
                </div>
            </div>
            <BottomNav />
        </div>
    )
}
