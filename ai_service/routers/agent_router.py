"""
Agent Router — Yojna Sathi Conversational Endpoint
FastAPI router for the multi-turn interview agent.

Session state is stored in-memory per session_id (for dev).
In production: use Redis or a DB-backed session store.
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
import logging

from ai_service.utils.auth import require_api_key
from ai_service.utils.rate_limiter import agent_limiter

from ai_service.agent.yojna_sathi import (
    UserProfile, get_next_question, parse_answer, score_eligibility
)

# Document types that require the user to upload proof during the interview
# Maps question id → expected doc type (for frontend camera trigger)
_DOC_QUESTION_MAP: dict[str, str] = {
    "is_bpl":          "ration_card",    # BPL Ration Card
    "has_house":       "land_record",    # Proof of residence / Khasra
    "disability":      "disability_cert",
    "is_ex_serviceman": "service_cert",
}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])

# ── In-memory session store {session_id: (UserProfile, current_question_id)} ──
_sessions: dict[str, dict] = {}

# Number of top schemes to return when interview completes
TOP_N_SCHEMES = 5


# ── Models ─────────────────────────────────────────────────────────────────────
class AgentStartResponse(BaseModel):
    session_id: str
    question: str
    question_hi: str
    progress_pct: int
    hint: str

class AgentAnswerRequest(BaseModel):
    session_id: str
    answer: str

class SchemeSuggestion(BaseModel):
    name: str
    sector: str
    state: str
    benefit: str
    apply_url: str
    eligibility_score: int
    apply_guide_url: Optional[str] = None   # /apply/guide?scheme_key=... (if wizard exists)

class AgentResponse(BaseModel):
    session_id: str
    done: bool
    question: Optional[str] = None
    question_hi: Optional[str] = None
    progress_pct: int
    schemes: Optional[list[SchemeSuggestion]] = None
    profile_summary: Optional[dict] = None
    message: Optional[str] = None
    # OCR trigger: if set, frontend shows camera/upload button for this doc type
    doc_requested: Optional[str] = None   # e.g. "aadhaar" | "ration_card" | None


# ── Routes ─────────────────────────────────────────────────────────────────────
@router.post("/start", response_model=AgentStartResponse, dependencies=[Depends(require_api_key)])
async def start_session(request: Request):
    """Start a new Yojna Sathi interview session."""
    agent_limiter.check(agent_limiter.get_client_ip(request))
    session_id = str(uuid.uuid4())
    profile = UserProfile()
    _sessions[session_id] = {"profile": profile, "question_idx": 0}

    first_q = get_next_question(profile)
    return AgentStartResponse(
        session_id=session_id,
        question=first_q["question_en"],
        question_hi=first_q["question_hi"],
        progress_pct=0,
        hint=_get_hint(first_q),
    )


@router.post("/answer", response_model=AgentResponse, dependencies=[Depends(require_api_key)])
async def answer_question(req: AgentAnswerRequest, request: Request):
    """Submit an answer and get the next question or final scheme recommendations."""
    agent_limiter.check(agent_limiter.get_client_ip(request))
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404,
            detail="Session not found. Call /agent/start first.")

    profile: UserProfile = session["profile"]

    # Parse the current answer
    current_q = get_next_question(profile)
    if current_q:
        parse_answer(current_q, req.answer, profile)

    # Get next question
    next_q = get_next_question(profile)
    progress = profile.completion_pct()

    # If interview is done (no more questions), retrieve schemes
    if next_q is None or progress >= 100:
        schemes = await _retrieve_schemes(profile)
        # Clean up session
        del _sessions[req.session_id]
        return AgentResponse(
            session_id=req.session_id,
            done=True,
            progress_pct=100,
            schemes=schemes,
            profile_summary=_profile_summary(profile),
            message=_build_summary_msg(profile, len(schemes)),
        )

    # Check if this question requires a document upload
    doc_requested = _DOC_QUESTION_MAP.get(next_q["id"])

    return AgentResponse(
        session_id=req.session_id,
        done=False,
        question=next_q["question_en"],
        question_hi=next_q["question_hi"],
        progress_pct=progress,
        doc_requested=doc_requested,
    )


@router.get("/session/{session_id}", response_model=AgentResponse)
async def get_session_status(session_id: str):
    """Get current session status and profile so far."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    profile: UserProfile = session["profile"]
    next_q = get_next_question(profile)
    return AgentResponse(
        session_id=session_id,
        done=next_q is None,
        question=next_q["question_en"] if next_q else None,
        question_hi=next_q["question_hi"] if next_q else None,
        progress_pct=profile.completion_pct(),
    )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a session (user wants to restart)."""
    _sessions.pop(session_id, None)
    return {"status": "cleared"}


def get_next_question_for_session(profile: UserProfile) -> Optional[dict]:
    """
    Public helper used by ocr_router to get the current question
    for a given profile (so OCR results can be injected as answers).
    """
    return get_next_question(profile)


# ── Helpers ────────────────────────────────────────────────────────────────────
async def _retrieve_schemes(profile: UserProfile) -> list[SchemeSuggestion]:
    """Query ChromaDB with the user's profile, re-rank by eligibility score."""
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        from pathlib import Path

        chroma_dir = Path(__file__).parent.parent / "chroma_db"
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        col = client.get_collection(name="yojna_setu_schemes", embedding_function=ef)

        query = profile.to_query_string()

        # Broader state filter: include Central + user's state if known
        where = None
        if profile.state:
            where = {"state": {"$in": [profile.state, "Central"]}}

        # Retrieve extra results for re-ranking
        results = col.query(
            query_texts=[query],
            n_results=TOP_N_SCHEMES * 3,  # retrieve 3x more, then re-rank
            where=where,
        )

        docs  = results["documents"][0]
        metas = results["metadatas"][0]

        suggestions = []
        for doc, meta in zip(docs, metas):
            score = score_eligibility(doc, profile)  # 0-100 eligibility score
            if score >= 40:
                benefit_line = ""
                for line in doc.split("\n"):
                    if line.startswith("Benefit:"):
                        benefit_line = line.replace("Benefit:", "").strip()
                        break

                # Check if a guided wizard exists for this scheme
                from ai_service.routers.apply_guide import _SCHEME_GUIDES
                scheme_key_guess = (
                    meta.get("name", "")
                    .lower()
                    .replace(" ", "")
                    .replace("-", "")
                )
                # Try to match against known keys
                guide_key = None
                for k in _SCHEME_GUIDES:
                    if k in scheme_key_guess or scheme_key_guess.startswith(k[:5]):
                        guide_key = k
                        break

                apply_guide_url = (
                    f"/apply/guide?scheme_key={guide_key}&state={profile.state or ''}"
                    if guide_key else None
                )

                suggestions.append(SchemeSuggestion(
                    name=meta.get("name", "Unknown Scheme"),
                    sector=meta.get("sector", ""),
                    state=meta.get("state", "Central"),
                    benefit=benefit_line[:200],
                    apply_url=meta.get("apply_url", ""),
                    eligibility_score=score,
                    apply_guide_url=apply_guide_url,
                ))

        # ── Re-rank: sort by eligibility score (highest first) ───────────────
        suggestions.sort(key=lambda x: x.eligibility_score, reverse=True)
        return suggestions[:TOP_N_SCHEMES]

    except Exception as e:
        logger.error(f"Scheme retrieval error: {e}")
        return []


def _get_hint(question: dict) -> str:
    hints = {
        "state": "E.g. Maharashtra, Rajasthan, Bihar...",
        "age":   "Enter your age as a number, e.g. 35",
        "gender": "Type: male / female (ya 'mahila' / 'purush')",
        "caste_category": "Type SC / ST / OBC / General",
        "occupation": "Type: farmer / student / salaried / unemployed / self_employed",
        "income_lpa": "Enter annual family income in lakhs, e.g. 1.5",
        "is_bpl": "Type: ha / nahi (yes / no)",
        "has_house": "Type: ha / nahi — kya aapka pakka ghar hai?",
        "disability": "Type: ha / nahi",
        "is_ex_serviceman": "Type: ha / nahi",
    }
    return hints.get(question["id"], "Please type your answer")


# ── /agent/checklist — document requirements for a scheme ─────────────────────
class ChecklistResponse(BaseModel):
    scheme_name: str
    sector: str
    state: str
    documents: list[str]
    apply_url: str
    tip: str


@router.get("/checklist", response_model=list[ChecklistResponse])
async def get_scheme_checklist(query: str, state: str = None, top_k: int = 3):
    """
    Returns document checklists for the most relevant schemes matching a query.
    Example: GET /agent/checklist?query=pm+kisan&state=Rajasthan
    """
    try:
        import chromadb, re
        from chromadb.utils import embedding_functions
        from pathlib import Path

        chroma_dir = Path(__file__).parent.parent / "chroma_db"
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        col = client.get_collection(name="yojna_setu_schemes", embedding_function=ef)

        where = {"state": {"$in": [state, "Central"]}} if state else None
        results = col.query(query_texts=[query], n_results=top_k, where=where)

        docs  = results["documents"][0]
        metas = results["metadatas"][0]

        checklists = []
        for doc, meta in zip(docs, metas):
            # Extract "Documents Required:" line from the stored text chunk
            docs_line = ""
            for line in doc.split("\n"):
                if line.lower().startswith("documents required:"):
                    docs_line = line.replace("Documents Required:", "").strip()
                    break

            doc_list = [d.strip() for d in docs_line.split(",") if d.strip()] if docs_line else []
            if not doc_list:
                doc_list = ["Aadhaar Card", "Bank Passbook", "Passport size photo"]

            checklists.append(ChecklistResponse(
                scheme_name=meta.get("name", ""),
                sector=meta.get("sector", ""),
                state=meta.get("state", "Central"),
                documents=doc_list,
                apply_url=meta.get("apply_url", ""),
                tip="Yeh documents lekar apne nazdiki CSC centre jayein ya upar diye link par online apply karein.",
            ))

        return checklists

    except Exception as e:
        logger.error(f"Checklist error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _profile_summary(profile: UserProfile) -> dict:
    d = {k: v for k, v in vars(profile).items() if v is not None and v != []}
    return d


def _build_summary_msg(profile: UserProfile, num_schemes: int) -> str:
    name = profile.name or "aap"
    state = profile.state or "aapke rajya"
    return (
        f"Bahut achha! {name} ke liye hum ne {num_schemes} sarkari "
        f"yojanaen {state} aur Central level par dhundhi hain. "
        f"Inhe dekhein aur apply karna na bhoolein! 🙏"
    )
