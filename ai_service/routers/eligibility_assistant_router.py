"""
eligibility_assistant_router.py — POST /eligibility-assistant/chat, and
POST /eligibility-assistant/voice for the spoken version of the same turn.

Deliberately PUBLIC, no auth dependency — unlike application_assistant_router
(which requires get_current_citizen_id), this is the same "learn before you
sign up" surface as CreditSchemeController's /eligibility endpoint in Spring
Boot: a citizen must be able to find out what they qualify for before
creating an account. Rate-limited by IP instead of citizen_id since there is
no citizen_id yet.

Both endpoints run the FULL 13-agent orchestrator (graph/chat_turn.py), not
just the eligibility assistant: a citizen in this chat can ask how to apply,
compare two schemes, file a grievance or check a status and reach the right
specialist. Credit-eligibility turns are routed by the classifier to the
`credit_eligibility` node, which wraps the deterministic slot-filling
assistant and calls Spring's real eligibility endpoint — no LLM ever
produces the verdict or its figures.

NOT stateless, despite the guest-facing surface: the orchestrator needs
conversation history between turns, so turns are persisted to
conversation_sessions under an anonymous `guest:<session_id>` id (see
_guest_citizen_id). The UI says so rather than promising otherwise.

/voice reuses the exact Sarvam STT/TTS primitives voice_conversation.py
already uses (Saaras v3 / Bulbul v3, 22+ languages, gTTS fallback). Unlike
voice_conversation.py this is UNAUTHENTICATED by design (guest-first, same
as /chat above), which is exactly the shape of endpoint a 2026-07-17
security sweep removed elsewhere in this codebase for being a cost/quota
abuse vector (paid Sarvam calls, no gate) — chat_limiter.check(ip) here is
that gate, not optional.
"""
import base64
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ai_service.db.mongo import ensure_indexes, get_db
from ai_service.graph.chat_turn import run_chat_turn
from ai_service.utils.rate_limiter import chat_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eligibility-assistant", tags=["eligibility-assistant"])

_indexes_ready = False

_SUPPORTED_AUDIO_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
_MAX_AUDIO_MB = 15  # a single chat turn's worth of speech, not a file upload


class EligibilityChatRequest(BaseModel):
    message: str
    language: str = "en"
    session_id: str | None = None
    # Kept for backward compatibility with the pre-orchestrator client, which
    # held slot state itself. Slot state now lives on the session document
    # (conversation_sessions.eligibilityContext) because the orchestrator
    # needs a session anyway to carry conversation history between turns.
    context: dict = {}


class EligibilityChatResponse(BaseModel):
    bot_reply: str
    session_id: str
    intent: str = ""
    results: dict | None = None
    context: dict = {}


async def _flow_active(db, session_id: str) -> bool:
    """True when a credit slot-filling flow is already under way this session.

    Feeds _route_by_intent's one narrow correction (see orchestrator.py): a
    bare answer to the question Sathi just asked carries no loan context of
    its own, so the classifier reads it as general scheme discovery and the
    citizen falls out of the flow with half their answers stranded.
    """
    session = await db["conversation_sessions"].find_one(
        {"sessionId": session_id}, {"eligibilityContext": 1},
    )
    slots = ((session or {}).get("eligibilityContext") or {}).get("slots") or {}
    return any(v is not None for v in slots.values())


def _guest_citizen_id(session_id: str) -> str:
    """A stable, anonymous identity for an unauthenticated StartGo visitor.

    The orchestrator needs a citizen_id to key session history and profile
    learning. Deriving it from the client's own session id keeps guest turns
    coherent across a conversation without inventing an account — and the
    `guest:` prefix makes these rows obviously non-citizen to anything reading
    the collection later. A guest has no CitizenProfile, so profile lookups
    simply return {} and every agent degrades to "ask, don't assume."
    """
    return f"guest:{session_id}"


@router.post("/chat", response_model=EligibilityChatResponse)
async def eligibility_chat(req: EligibilityChatRequest, request: Request):
    """Routes through the FULL 13-agent orchestrator, not just the eligibility
    assistant — so a citizen in this chat can also ask how to apply, compare
    two schemes, file a grievance or check a status, and get the right
    specialist, instead of the assistant only understanding eligibility.

    Credit-eligibility turns still land on the deterministic path: the
    classifier routes them to the `credit_eligibility` node, which wraps
    EligibilityAssistant and calls Spring's real eligibility endpoint. No LLM
    produces the verdict or its figures — see that agent's module docstring.
    """
    client_ip = request.client.host if request.client else "unknown"
    chat_limiter.check(client_ip)

    global _indexes_ready
    session_id = req.session_id or str(uuid4())
    db = get_db()
    if not _indexes_ready:
        await ensure_indexes()
        _indexes_ready = True

    result = await run_chat_turn(
        db,
        citizen_id=_guest_citizen_id(session_id),
        session_id=session_id,
        message=req.message,
        channel="web",
        lang=req.language or "en",
        profile={},  # guests have no stored profile — agents must ask, not assume
        extra_state={"eligibility_flow_active": await _flow_active(db, session_id)},
    )

    results = result.get("credit_eligibility_results")
    if results:
        logger.info("Eligibility chat: results returned (verdict=%s)", results.get("verdict"))

    return EligibilityChatResponse(
        bot_reply=result["reply"],
        session_id=session_id,
        intent=result.get("intent", ""),
        results=results,
    )


@router.post("/voice")
async def eligibility_voice(
    request: Request,
    audio: UploadFile = File(..., description="Citizen's spoken message (WAV/MP3/M4A/WEBM/OGG)"),
    session_id: str = Form("", description="Conversation session id — same one /chat uses"),
    context: str = Form("{}", description="Deprecated; slot state lives on the session document now"),
    language: str = Form("en", description="UI-selected language, e.g. 'en'|'hi'|'bn'|'ta'|'te'|'mr'"),
):
    """One spoken turn: transcribe -> the SAME orchestrator turn /chat runs ->
    speak the reply. Sharing session_id with /chat means speaking and typing
    continue one conversation, not two — the same continuity
    voice_conversation.py established for the main app.

    JSON response (not a raw audio Response like voice_conversation.py's
    /answer) because the results payload is a full nested object that doesn't
    fit HTTP headers — that module's header-encoding trick is right-sized for
    a few short strings, not this."""
    client_ip = request.client.host if request.client else "unknown"
    chat_limiter.check(client_ip)

    suffix = Path(audio.filename or "audio.webm").suffix.lower()
    if suffix not in _SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(400, f"Unsupported audio format: {suffix}")
    content = await audio.read()
    if len(content) / (1024 * 1024) > _MAX_AUDIO_MB:
        raise HTTPException(400, f"Audio too large (max {_MAX_AUDIO_MB}MB)")

    from ai_service.utils.sarvam import get_sarvam_lang_code, sarvam_transcribe, speak_for_state

    lang_hint = get_sarvam_lang_code(language)
    try:
        transcribed = sarvam_transcribe(content, audio_format=suffix.lstrip("."), language_code=lang_hint)
    except Exception as e:
        logger.warning("Eligibility voice: transcription failed (%s: %s)", e.__class__.__name__, e)
        raise HTTPException(502, "Could not transcribe that — please try again.")

    transcript = (transcribed.get("transcript") or "").strip()
    detected_lang = transcribed.get("language_code") or lang_hint

    if len(transcript) < 2:
        # Same "didn't catch that" contract as voice_conversation.py's /answer,
        # but as JSON — nothing to hand off to EligibilityAssistant with no words.
        retry_text = {
            "en": "Sorry, I didn't catch that clearly. Please try again.",
            "hi": "Maafi kijiye, saaf nahi suna. Kripya dobara bolein.",
        }.get(language, "Sorry, I didn't catch that clearly. Please try again.")
        audio_bytes = speak_for_state(retry_text, force_lang_code=detected_lang)
        return {
            "transcript": "", "bot_reply": retry_text, "session_id": session_id, "results": None,
            "audio_base64": base64.b64encode(audio_bytes).decode(), "detected_language": detected_lang,
        }

    global _indexes_ready
    sid = session_id or str(uuid4())
    db = get_db()
    if not _indexes_ready:
        await ensure_indexes()
        _indexes_ready = True

    turn = await run_chat_turn(
        db,
        citizen_id=_guest_citizen_id(sid),
        session_id=sid,
        message=transcript,
        channel="voice",
        lang=language or "en",
        profile={},
    )
    results = turn.get("credit_eligibility_results")

    try:
        audio_bytes = speak_for_state(turn["reply"], force_lang_code=detected_lang)
        audio_b64 = base64.b64encode(audio_bytes).decode()
    except Exception as e:
        logger.warning("Eligibility voice: TTS failed (%s: %s) — returning text only", e.__class__.__name__, e)
        audio_b64 = None

    if results:
        logger.info("Eligibility voice: results returned (verdict=%s)", results.get("verdict"))

    return {
        "transcript": transcript,
        "bot_reply": turn["reply"],
        "session_id": sid,
        "intent": turn.get("intent", ""),
        "results": results,
        "audio_base64": audio_b64,
        "detected_language": detected_lang,
    }
