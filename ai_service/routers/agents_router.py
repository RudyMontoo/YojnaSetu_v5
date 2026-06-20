"""
agents_router.py — dedicated REST endpoints for agents that don't fit the
chat-intent routing model (per CLAUDE.md, document verification, financial
planning, grievance, and CSC assist are all separate multipart/JSON
endpoints, not something routed through /orchestrator/chat's intent
classifier). Implemented here: Agent 4 (PPO mismatch), Agent 7 (financial
plan), Agent 9 (CSC alternatives), Agent 10 (analytics), plus the
observability endpoints /agents/health and /agents/trace/{session_id}.
Agent 5's dedicated endpoint is future work.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ai_service.db.mongo import get_db
from ai_service.graph.agents.analytics import generate_weekly_report
from ai_service.graph.agents.csc_assist import suggest_doc_alternatives
from ai_service.graph.agents.document_verification import verify_ppo_aadhaar_match
from ai_service.graph.agents.financial_planning import build_financial_plan
from ai_service.graph.agents.grievance import record_grievance
from ai_service.routers.ocr_router import _run_ocr
from ai_service.utils.auth import require_api_key
from ai_service.utils.jwt_auth import get_current_admin_id, get_current_citizen_id, get_current_operator_id
from ai_service.utils.rate_limiter import ocr_limiter
from ai_service.utils.spring_client import fetch_citizen_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


class PpoVerifyResponse(BaseModel):
    checked: bool
    reason: str | None = None
    name_aadhaar: str | None = None
    name_ppo: str | None = None
    dob_aadhaar: str | None = None
    dob_ppo: str | None = None
    m_ppo: float | None = None
    name_mismatch: bool | None = None
    dob_mismatch: bool | None = None
    blocks_dlc_submission: bool | None = None
    reply: str | None = None


@router.post("/document/verify-ppo", response_model=PpoVerifyResponse, dependencies=[Depends(require_api_key)])
async def verify_ppo(
    request: Request,
    aadhaar_file: Annotated[UploadFile, File(description="Aadhaar card image")],
    ppo_file: Annotated[UploadFile, File(description="PPO (Pension Payment Order) document image")],
):
    """
    Agent 4's v5.0 PPO/Aadhaar mismatch check. Named distinctly from
    CLAUDE.md's general single-document `/agents/document/verify` endpoint
    (document authenticity/sufficiency, not built in this pass) since this
    one genuinely needs two documents to compare against each other.

    Zero-retention: both images are OCR'd in memory and discarded; only the
    extracted names/DOBs and the mismatch result are returned.
    """
    ocr_limiter.check(ocr_limiter.get_client_ip(request))  # shared with /ocr/scan — 10/min, heavy CPU

    for f in (aadhaar_file, ppo_file):
        if f.content_type not in {"image/jpeg", "image/png", "image/webp", "image/jpg"}:
            raise HTTPException(status_code=415, detail=f"{f.filename}: unsupported type {f.content_type}. Use JPEG/PNG/WEBP.")

    aadhaar_bytes = await aadhaar_file.read()
    ppo_bytes = await ppo_file.read()
    if len(aadhaar_bytes) > 20 * 1024 * 1024 or len(ppo_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Max 20MB per file.")

    aadhaar_text = await _run_ocr(aadhaar_bytes)
    ppo_text = await _run_ocr(ppo_bytes)
    del aadhaar_bytes, ppo_bytes

    result = await verify_ppo_aadhaar_match(aadhaar_text, ppo_text)
    return PpoVerifyResponse(**result)


class FinancialPlanResponse(BaseModel):
    total_annual_benefit_inr: float
    schemes_considered: int
    breakdown: list[dict]
    calendar: dict
    contingent_benefits: list[dict]
    ranked_by_benefit_effort_ratio: list[dict]
    reply: str


# Static registry of the agent fleet — which exist, and where their liveness
# signal comes from. reasoning_traces carry agent_name for everything routed
# through the orchestrator graph; Agent 2/10 leave different footprints.
_AGENT_REGISTRY = {
    # trace_names deliberately empty: every chat turn produces SOME trace, so
    # orchestrator liveness = newest trace of any kind (see the elif below) —
    # scoping it to placeholder traces made "orchestrator health" mean "how
    # recently did someone hit an unbuilt feature", which is backwards.
    "orchestrator": {"built": True, "trace_names": []},
    "agent1_eligibility": {"built": True, "trace_names": ["agent1_eligibility"]},
    "agent2_discovery": {"built": True, "trace_names": []},  # liveness from schemes.lastUpdated
    "agent3_guidance": {"built": True, "trace_names": ["agent3_guidance"]},
    "agent4_document": {"built": True, "trace_names": ["agent4_document"]},
    "agent5_grievance": {"built": True, "trace_names": ["agent5_grievance"]},
    "agent6_nudge": {"built": False, "trace_names": []},
    "agent7_financial": {"built": True, "trace_names": ["agent7_financial"]},
    "agent8_comparison": {"built": True, "trace_names": ["agent8_comparison"]},
    "agent9_csc": {"built": True, "trace_names": ["agent9_csc"]},
    "agent10_analytics": {"built": True, "trace_names": []},  # liveness from admin_reports
    "agent11_biometric": {"built": False, "trace_names": []},
    "agent12_offline_proof": {"built": False, "trace_names": []},
}

_STALE_AFTER_HOURS = 48


@router.get("/health", dependencies=[Depends(require_api_key), Depends(get_current_admin_id)])
async def agents_health():
    """
    CLAUDE.md: GET /agents/health — Admin JWT — status of all agents:
    {agent_name, status: green/yellow/red, last_active}. Honest statuses:
    - not_built: agent doesn't exist yet (better than a fake red)
    - green:     built, no unresolved agent_alerts
    - yellow:    built but has unresolved agent_alerts, or no activity in 48h
    - red:       built with unresolved alerts AND no recent activity
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(hours=_STALE_AFTER_HOURS)

    # unresolved alerts per agent, one query
    alert_counts: dict[str, int] = {}
    async for doc in db["agent_alerts"].aggregate([
        {"$match": {"resolved": False}},
        {"$group": {"_id": "$agent_name", "count": {"$sum": 1}}},
    ]):
        alert_counts[doc["_id"]] = doc["count"]

    statuses = []
    for agent_name, meta in _AGENT_REGISTRY.items():
        if not meta["built"]:
            statuses.append({"agent_name": agent_name, "status": "not_built", "last_active": None, "unresolved_alerts": 0})
            continue

        last_active = None
        if meta["trace_names"]:
            trace = await db["reasoning_traces"].find_one(
                {"agent_name": {"$in": meta["trace_names"]}}, {"at": 1}, sort=[("at", -1)])
            last_active = trace["at"] if trace else None
        elif agent_name == "agent2_discovery":
            doc = await db["schemes"].find_one({"discoverySource": {"$exists": True}}, {"lastUpdated": 1}, sort=[("lastUpdated", -1)])
            last_active = doc.get("lastUpdated") if doc else None
        elif agent_name == "agent10_analytics":
            doc = await db["admin_reports"].find_one({}, {"report_date": 1}, sort=[("report_date", -1)])
            last_active = doc.get("report_date") if doc else None
        elif agent_name == "orchestrator":
            trace = await db["reasoning_traces"].find_one({}, {"at": 1}, sort=[("at", -1)])
            last_active = trace["at"] if trace else None

        alerts = alert_counts.get(agent_name, 0)
        # Mongo returns naive datetimes — normalize before comparing
        active_recent = last_active is not None and last_active.replace(tzinfo=timezone.utc) >= stale_cutoff
        if alerts and not active_recent:
            status = "red"
        elif alerts or not active_recent:
            status = "yellow"
        else:
            status = "green"

        statuses.append({
            "agent_name": agent_name,
            "status": status,
            "last_active": last_active.isoformat() if last_active else None,
            "unresolved_alerts": alerts,
        })

    return {"agents": statuses, "checked_at": now.isoformat()}


@router.get("/trace/{session_id}", dependencies=[Depends(require_api_key)])
async def get_trace(session_id: str, citizen_id: str = Depends(get_current_citizen_id)):
    """
    CLAUDE.md: GET /agents/trace/{session_id} — Citizen JWT — full reasoning
    trace. Ownership is enforced via the session document's userId, NOT
    trusted from the path — session UUIDs are guessable enough that skipping
    this check would let any citizen read any other citizen's reasoning
    traces (which include their profile-derived query text).
    """
    db = get_db()
    session = await db["conversation_sessions"].find_one({"sessionId": session_id}, {"userId": 1})
    if not session or session.get("userId") != citizen_id:
        # 404 for both missing and not-yours — don't leak which sessions exist
        raise HTTPException(status_code=404, detail="Session not found")

    traces = await db["reasoning_traces"].find(
        {"session_id": session_id}, {"_id": 0}, sort=[("at", 1)]
    ).to_list(length=500)
    for t in traces:
        if isinstance(t.get("at"), datetime):
            t["at"] = t["at"].isoformat()
    return {"session_id": session_id, "trace": traces}


@router.post("/admin/analytics/run", dependencies=[Depends(require_api_key)])
async def run_analytics(admin_id: str = Depends(get_current_admin_id)):
    """
    Agent 10 — manual trigger. The real deployment target is a weekly
    Sunday-11PM-IST Cloud Run Job (CLAUDE.md); this endpoint exists so the
    report can be generated on demand and so the whole path is testable
    before any cron infrastructure exists. Metrics are pure Mongo
    aggregations (LLM only writes the narrative, with a template fallback).
    """
    report = await generate_weekly_report(get_db())
    logger.info("Agent 10 report triggered manually by admin %s", admin_id)
    return report


@router.get("/admin/analytics/latest", dependencies=[Depends(require_api_key), Depends(get_current_admin_id)])
async def latest_analytics():
    """CLAUDE.md: GET /admin/agents/analytics/latest — Admin JWT — latest
    Agent 10 weekly report. (Mounted under /agents, so the full path is
    /agents/admin/analytics/latest.)"""
    report = await get_db()["admin_reports"].find_one({}, {"_id": 0}, sort=[("report_date", -1)])
    if not report:
        raise HTTPException(status_code=404, detail="No analytics report generated yet — POST /agents/admin/analytics/run first.")
    return report


class GrievanceRequest(BaseModel):
    complaint_description: str
    scheme_code: str | None = None
    external_app_id: str | None = None


@router.post("/grievance", dependencies=[Depends(require_api_key)])
async def file_grievance(req: GrievanceRequest, citizen_id: str = Depends(get_current_citizen_id)):
    """
    Agent 5 — CLAUDE.md: POST /agents/grievance, Citizen JWT. Records the
    grievance durably + returns CPGRAMS self-filing guidance; pgportal
    browser automation is not built yet (the record's status field is the
    handoff point when it lands). Body deviation from CLAUDE.md noted:
    scheme_code, not scheme_id — consistent with every other endpoint.
    """
    result = await record_grievance(
        get_db(), citizen_id=citizen_id,
        complaint_description=req.complaint_description,
        scheme_code=req.scheme_code, external_app_id=req.external_app_id,
    )
    return result


class CscAlternativesRequest(BaseModel):
    scheme_code: str
    missing_doc_type: str


class CscAlternativesResponse(BaseModel):
    scheme_name: str
    has_alternatives: bool
    alternatives: list[dict]
    mandatory_no_substitute: bool
    operator_advice: str


@router.post("/csc/alternatives", response_model=CscAlternativesResponse, dependencies=[Depends(require_api_key)])
async def csc_alternatives(req: CscAlternativesRequest, operator_id: str = Depends(get_current_operator_id)):
    """
    Agent 9 — CSC Assist, per CLAUDE.md: 'Operator JWT — body: {scheme_id,
    missing_doc_type}'. Role-gated: a valid CITIZEN token gets 403 here —
    the role claim rides inside the RS256-signed token, so no extra lookup.
    Uses scheme_code (not Mongo _id) consistent with the rest of the API.
    """
    result = await suggest_doc_alternatives(get_db(), req.scheme_code, req.missing_doc_type)
    if not result.pop("found"):
        raise HTTPException(status_code=404, detail=f"Unknown scheme_code: {req.scheme_code}")
    logger.info("Agent 9: operator %s asked alternatives for %s / %r", operator_id, req.scheme_code, req.missing_doc_type)
    return CscAlternativesResponse(**result)


@router.get("/financial-plan", response_model=FinancialPlanResponse, dependencies=[Depends(require_api_key)])
async def financial_plan(citizen_id: str = Depends(get_current_citizen_id)):
    """
    Agent 7 — Financial Planning, per CLAUDE.md's spec: GET, citizen
    identity from JWT, no body. Previously POST with citizen_id/profile
    accepted directly in the request body as a dev-mode stand-in (any
    caller could request any citizen's plan) — now citizen_id comes from
    the signature-verified access_token cookie, and profile is fetched
    from Spring Boot's internal profile endpoint.
    """
    profile = await fetch_citizen_profile(citizen_id)
    result = await build_financial_plan(profile, get_db())
    return FinancialPlanResponse(**result)
