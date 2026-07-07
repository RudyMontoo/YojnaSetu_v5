"""
Voice Conversation Router — bridges spoken audio to the real 12-agent
LangGraph orchestrator (ai_service/graph/), the same brain text chat uses
via /orchestrator/chat and /ws/session/{id}.

Rewritten 2026-07-07: previously this router spoke real audio (Sarvam
Saaras v3 STT / Bulbul v3 TTS — that part was already correct) but ran it
through the OLD pre-rebuild fixed-questionnaire interview
(agent_router.py's UserProfile/_sessions + ChromaDB retrieval) instead of
the orchestrator. That meant a citizen using voice got a completely
different, weaker experience than text chat: no eligibility deep-dive, no
financial plan, no comparison, no grievance filing, no CSC assist, no
small_talk handling, nothing persisted to conversation_sessions, no
profile learning. Voice and text now share one brain — only the
transport (audio in, audio out) differs.

Endpoints:
  POST /voice/conversation/start   → JWT-gated. Speaks a localized canned
                                      welcome. No orchestrator call — this
                                      is just "hello, go ahead and speak."
  POST /voice/conversation/answer  → JWT-gated. Transcribes audio (Sarvam),
                                      runs the transcript through the same
                                      run_chat_turn() as REST/WS text chat,
                                      speaks the reply back (Sarvam).

Session continuity: session_id is CLIENT-supplied (same UUID the frontend
already generates for text chat, see ChatPage.jsx's ensureSessionId()) —
not server-generated like the old flow. This means speaking and typing in
the same tab continue the SAME conversation thread in Mongo, rather than
voice living in a separate session space.

Auth: get_current_citizen_id (utils/jwt_auth.py), same as every other
citizen-scoped endpoint — the old flow had none at all, which was fine
when it only touched in-memory state, but now that it writes to
conversation_sessions/reasoning_traces/trend_events and reads/learns the
citizen profile, real identity is required, not optional.

The removed `/voice/conversation/chat` endpoint (one-shot, no session) is
not replaced: it referenced an undefined `language` variable (a real bug —
would have thrown NameError on every call) and had zero callers in the
frontend. `/answer` covers the same need with a session.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import Response

from ai_service.db.mongo import ensure_indexes, get_db
from ai_service.graph.chat_turn import run_chat_turn
from ai_service.utils.jwt_auth import get_current_citizen_id
from ai_service.utils.spring_client import fetch_citizen_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice/conversation", tags=["voice_agent"])

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
MAX_FILE_MB = 25

WELCOME_TEXT_HI = (
    "Namaskar! Main Sathi hun, aapki madad ke liye. Kripya bataiye — "
    "aap kaunsi yojna ke baare mein jaanna chahte hain?"
)

_indexes_ready = False


def safe_header(value: str, max_len: int = 300) -> str:
    """URL-encode non-ASCII chars so they fit in latin-1 HTTP headers."""
    from urllib.parse import quote
    return quote(str(value)[:max_len], safe=" ,|.-_")


def _speak(text: str, state: Optional[str] = None, lang_code: Optional[str] = None) -> bytes:
    """Sarvam Bulbul v3 TTS. speak_for_state() has its own internal
    Sarvam-outage -> gTTS fallback (Hindi/English only, not full 22-language
    coverage) — a resilience feature of that helper, not something this
    router adds or hides."""
    from ai_service.utils.sarvam import speak_for_state
    return speak_for_state(text, state=state, force_lang_code=lang_code)


async def _transcribe_upload(file: UploadFile, state: Optional[str] = None) -> tuple[str, str]:
    """Sarvam Saaras v3 STT. Returns (transcript, detected_language_code e.g. 'hi-IN')."""
    from pathlib import Path
    suffix = Path(file.filename or "audio.wav").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"Unsupported audio format: {suffix}")
    content = await file.read()
    if len(content) / (1024 * 1024) > MAX_FILE_MB:
        raise HTTPException(400, "Audio too large (max 25MB)")

    from ai_service.utils.sarvam import get_language_for_state, get_sarvam_lang_code, sarvam_transcribe

    # Language hint: known state → its language; else let Sarvam auto-detect
    # across its 22+ supported languages (it handles "unknown" natively).
    lang_code = get_sarvam_lang_code(get_language_for_state(state)) if state else "unknown"
    result = sarvam_transcribe(content, audio_format=suffix.lstrip("."), language_code=lang_code)
    return result["transcript"], result["language_code"]


@router.post("/start")
async def voice_start_session(state: Optional[str] = Form(default=None)):
    """Speaks a localized welcome. Stateless — the real session begins
    with the citizen's first /answer call, keyed by the session_id the
    frontend already generates for text chat."""
    audio_bytes = _speak(WELCOME_TEXT_HI, state=state)
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=welcome.mp3"},
    )


@router.post("/answer")
async def voice_answer(
    audio: UploadFile = File(..., description="Citizen's spoken message (WAV/MP3/M4A/WEBM)"),
    session_id: str = Form(..., description="Conversation session id — same one used for text chat"),
    citizen_id: str = Depends(get_current_citizen_id),
):
    """One voice turn: transcribe -> run through the real orchestrator ->
    speak the reply. Mirrors orchestrator_router.py's REST /chat exactly,
    just with audio in and audio out instead of JSON."""
    global _indexes_ready
    db = get_db()
    if not _indexes_ready:
        await ensure_indexes()
        _indexes_ready = True

    profile = await fetch_citizen_profile(citizen_id)

    transcript, detected_lang = await _transcribe_upload(audio, state=profile.get("state"))
    lang_2char = (detected_lang or "hi-IN").split("-")[0]

    if not transcript or len(transcript.strip()) < 2:
        audio_bytes = _speak(
            "Maafi kijiye, clearly nahi suna. Kripya dobara bolein.",
            state=profile.get("state"), lang_code=detected_lang,
        )
        return Response(
            content=audio_bytes, media_type="audio/mpeg",
            headers={
                "X-Session-Id": session_id,
                "X-Transcript": safe_header("(unclear)"),
                "X-Detected-Language": lang_2char,
            },
        )

    result = await run_chat_turn(
        db, citizen_id=citizen_id, session_id=session_id, message=transcript,
        channel="voice", lang=lang_2char, profile=profile,
    )

    audio_bytes = _speak(result["reply"], state=profile.get("state"), lang_code=detected_lang)

    scheme_names = " | ".join(s.get("name", "") for s in (result.get("active_schemes") or [])[:3])

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "X-Session-Id": session_id,
            "X-Transcript": safe_header(transcript),
            "X-Reply": safe_header(result["reply"]),
            "X-Intent": result.get("intent", ""),
            "X-Detected-Language": lang_2char,
            "X-Schemes": safe_header(scheme_names),
            "Content-Disposition": "inline; filename=reply.mp3",
        },
    )


@router.get("/test-tts")
async def test_tts(text: str = "Namaskar! Main Sathi hun.", state: Optional[str] = None):
    """Debug utility — no auth, no data access, just synthesizes arbitrary
    text. Kept from the previous version for manual Sarvam voice testing."""
    audio_bytes = _speak(text, state=state)
    return Response(
        content=audio_bytes, media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=test.mp3"},
    )
