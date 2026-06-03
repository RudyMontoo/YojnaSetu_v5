"""
FastAPI Chat Router — Yojna Setu
/chat endpoint: Hinglish scheme chatbot with:
  - Per-session conversation memory
  - No-match hallucination guard
  - Streaming support (/chat/stream)
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from typing import Optional
import logging

from ai_service.utils.auth import require_api_key
from ai_service.utils.rate_limiter import chat_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

_rag_chain = None

def get_chain():
    global _rag_chain
    if _rag_chain is None:
        from ai_service.rag_chain import build_rag_chain
        _rag_chain = build_rag_chain()
    return _rag_chain


# ── Request / Response models ──────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"   # for conversation memory
    state: Optional[str] = None             # e.g. "Rajasthan"
    sector: Optional[str] = None            # e.g. "health"
    language: Optional[str] = "hinglish"

    @field_validator("message")
    @classmethod
    def message_length(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("Message too long. Maximum 2000 characters allowed.")
        return v

class SchemeMatch(BaseModel):
    id: str
    name: str
    benefit: str
    sector: str
    state: str
    apply_url: str

class ChatResponse(BaseModel):
    reply: str
    language: str
    matched_schemes: list[SchemeMatch]
    session_id: str


# ── Helper ─────────────────────────────────────────────────────────────────────
def build_filters(state: Optional[str], sector: Optional[str]) -> Optional[dict]:
    conditions = []
    if state:
        conditions.append({"state": {"$in": [state, "Central"]}})
    if sector:
        conditions.append({"sector": {"$eq": sector}})
    if len(conditions) == 1:
        return conditions[0]
    if len(conditions) > 1:
        return {"$and": conditions}
    return None


def _make_slug(name: str) -> str:
    """Convert scheme name to a URL-safe slug."""
    import re
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def fetch_matched_schemes(query: str, filters: Optional[dict]) -> list[SchemeMatch]:
    """Query ChromaDB directly for structured scheme metadata."""
    try:
        import chromadb
        from pathlib import Path
        from chromadb.utils import embedding_functions

        chroma_dir = Path(__file__).parent.parent / "chroma_db"
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        collection = client.get_collection(name="yojna_setu_schemes", embedding_function=ef)
        results = collection.query(
            query_texts=[query], n_results=3,
            where=filters if filters else None,
        )
        matched = []
        for meta in (results.get("metadatas") or [[]])[0]:
            name = meta.get("name", "")
            matched.append(SchemeMatch(
                id=_make_slug(name) or "scheme",
                name=name,
                benefit=meta.get("benefit", meta.get("description", "Sarkari yojana ka labh")[:120]),
                sector=meta.get("sector", ""),
                state=meta.get("state", "Central"),
                apply_url=meta.get("apply_url", "https://india.gov.in"),
            ))
        return matched
    except Exception as e:
        logger.warning(f"Scheme metadata fetch failed: {e}")
        return []



# ── Standard chat route (with memory) ─────────────────────────────────────────
@router.post("/", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(req: ChatRequest, request: Request):
    chat_limiter.check(chat_limiter.get_client_ip(request))
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        from ai_service.rag_chain import invoke_with_memory
        chain   = get_chain()
        filters = build_filters(req.state, req.sector)

        # Invoke with per-session memory + no-match guard built-in
        reply = invoke_with_memory(
            chain,
            question=req.message,
            session_id=req.session_id or "default",
            filters=filters,
        )

        matched = fetch_matched_schemes(req.message, filters)

        return ChatResponse(
            reply=reply,
            language=req.language or "hinglish",
            matched_schemes=matched,
            session_id=req.session_id or "default",
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Streaming chat route ───────────────────────────────────────────────────────
@router.post("/stream", dependencies=[Depends(require_api_key)])
async def chat_stream(req: ChatRequest, request: Request):
    """
    Streaming version — yields tokens as they arrive from Gemini.
    Frontend can use EventSource or fetch with ReadableStream.
    """
    chat_limiter.check(chat_limiter.get_client_ip(request))
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        from ai_service.rag_chain import get_retriever, get_memory, NO_MATCH_RESPONSE
        chain   = get_chain()
        filters = build_filters(req.state, req.sector)
        history = get_memory(req.session_id or "default")  # InMemoryChatMessageHistory

        context_text = get_retriever()(req.message, filters)

        # No-match guard for streaming
        if context_text.strip() == "No matching schemes found.":
            async def no_match_gen():
                yield NO_MATCH_RESPONSE
            return StreamingResponse(no_match_gen(), media_type="text/plain")

        chat_messages = history.messages

        async def token_generator():
            full_response = ""
            for chunk in chain.stream({
                "question":     req.message,
                "filters":      filters,
                "chat_history": chat_messages,
            }):
                full_response += chunk
                yield chunk
            # Save to memory after streaming completes
            history.add_user_message(req.message)
            history.add_ai_message(full_response)

        return StreamingResponse(token_generator(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Stream error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Clear session memory ───────────────────────────────────────────────────────
@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation memory for a session (fresh start)."""
    from ai_service.rag_chain import clear_memory
    clear_memory(session_id)
    return {"status": "cleared", "session_id": session_id}


# ── Health check ───────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"status": "ok", "service": "rag_chat"}
