"""
orchestrator_router.py — REST entry point into the new LangGraph Orchestrator
(ai_service/graph/orchestrator.py), separate from the existing /chat router
(rag_chain.py + ChromaDB) so the old path keeps working while this one is
proven out. CLAUDE.md's long-term target is a WSS endpoint
(/ws/session/{session_id}); this REST endpoint is the first-session
verification surface — a WebSocket wrapper is a small follow-up once this
path is trusted, not done here.

Auth: reuses the existing require_api_key dependency (utils/auth.py) as a
service-level gate, plus get_current_citizen_id (utils/jwt_auth.py) which
verifies Spring Boot's RS256 access_token cookie and derives citizen_id from
the signature-verified token — this used to be a client-supplied field on
ChatRequest, trusted at face value, letting any caller act as any citizen.
If `profile` isn't supplied in the body, it's fetched from Spring Boot's
internal profile endpoint instead of defaulting to empty.
"""
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ai_service.db.mongo import ensure_indexes, get_db
from ai_service.discovery.agent2 import run_discovery
from ai_service.graph.chat_turn import run_chat_turn
from ai_service.utils.auth import require_api_key
from ai_service.utils.jwt_auth import get_current_citizen_id
from ai_service.utils.spring_client import fetch_citizen_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    channel: str = "web"
    lang: str = "hi"
    profile: dict = {}


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    active_schemes: list[dict]


_indexes_ready = False


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, citizen_id: str = Depends(get_current_citizen_id)):
    global _indexes_ready
    db = get_db()
    if not _indexes_ready:
        await ensure_indexes()
        _indexes_ready = True
    session_id = req.session_id or str(uuid4())

    profile = req.profile or await fetch_citizen_profile(citizen_id)

    result = await run_chat_turn(
        db,
        citizen_id=citizen_id,
        session_id=session_id,
        message=req.message,
        channel=req.channel,
        lang=req.lang,
        profile=profile,
    )

    return ChatResponse(session_id=session_id, **result)


@router.post("/admin/discovery/run", dependencies=[Depends(require_api_key)])
async def trigger_discovery(myscheme_limit: int | None = None):
    """Manual trigger for Agent 2 Discovery — the real deployment target is a
    scheduled Cloud Run Job (every 30min per CLAUDE.md), not a citizen-facing
    endpoint. Same require_api_key dependency as everything else for now;
    real admin-role gating is Phase 1 (Spring Boot OTP/JWT) work.

    myscheme_limit is omitted by default (PIB/data.gov.in only, fast) since a
    full MyScheme sync takes hours at the mandatory 2s rate limit — pass e.g.
    ?myscheme_limit=20 for a bounded test batch."""
    summary = await run_discovery(get_db(), myscheme_limit=myscheme_limit)
    return summary
