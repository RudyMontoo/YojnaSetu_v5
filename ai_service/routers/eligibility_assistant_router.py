"""
eligibility_assistant_router.py — POST /eligibility-assistant/chat, and
POST /eligibility-assistant/voice for the spoken version of the same turn.

Deliberately PUBLIC, no auth dependency — unlike application_assistant_router
(which requires get_current_citizen_id), this is the same "learn before you
sign up" surface as CreditSchemeController's /eligibility endpoint in Spring
Boot: a citizen must be able to find out what they qualify for before
creating an account. Rate-limited by IP instead of citizen_id since there is
no citizen_id yet.

Stateless: the client holds `context` between turns (see
services/eligibility_assistant.py's module docstring for why) and sends it
back each request. Nothing is written to Mongo here.

/voice reuses the exact Sarvam STT/TTS primitives voice_conversation.py
already uses (Saaras v3 / Bulbul v3, 22+ languages, gTTS fallback), but
routes the transcript through EligibilityAssistant instead of the general
12-agent orchestrator — same "never guess eligibility" contract as /chat,
just with audio in and audio out. Unlike voice_conversation.py this is
UNAUTHENTICATED by design (guest-first, same as /chat above), which is
exactly the shape of endpoint a 2026-07-17 security sweep removed elsewhere
in this codebase for being a cost/quota-abuse vector (paid Sarvam calls, no
gate) — chat_limiter.check(ip) here is that gate, not optional.
"""
import base64
import json
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from ai_service.services.eligibility_assistant import EligibilityAssistant
from ai_service.utils.rate_limiter import chat_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/eligibility-assistant", tags=["eligibility-assistant"])

_SUPPORTED_AUDIO_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
_MAX_AUDIO_MB = 15  # a single chat turn's worth of speech, not a file upload


class EligibilityChatRequest(BaseModel):
    message: str
    language: str = "en"
    context: dict = {}


class EligibilityChatResponse(BaseModel):
    bot_reply: str
    context: dict
    results: dict | None = None


@router.post("/chat", response_model=EligibilityChatResponse)
async def eligibility_chat(req: EligibilityChatRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    chat_limiter.check(client_ip)

    assistant = EligibilityAssistant()
    result = await assistant.process_message(req.message, req.language, req.context)

    if result["results"]:
        logger.info("Eligibility assistant: results returned (verdict=%s)", result["results"].get("verdict"))

    return EligibilityChatResponse(
        bot_reply=result["bot_reply"], context=result["context"], results=result["results"],
    )


@router.post("/voice")
async def eligibility_voice(
    request: Request,
    audio: UploadFile = File(..., description="Citizen's spoken message (WAV/MP3/M4A/WEBM/OGG)"),
    context: str = Form("{}", description="JSON-encoded context from the previous turn"),
    language: str = Form("en", description="UI-selected language, e.g. 'en'|'hi'|'bn'|'ta'|'te'|'mr'"),
):
    """One spoken turn: transcribe -> the same EligibilityAssistant.process_message()
    /chat uses -> speak the reply. JSON response (not a raw audio Response like
    voice_conversation.py's /answer) because context/results here are full nested
    objects that don't fit HTTP headers — voice_conversation.py's header-encoding
    trick is right-sized for a few short strings, not this."""
    client_ip = request.client.host if request.client else "unknown"
    chat_limiter.check(client_ip)

    suffix = Path(audio.filename or "audio.webm").suffix.lower()
    if suffix not in _SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(400, f"Unsupported audio format: {suffix}")
    content = await audio.read()
    if len(content) / (1024 * 1024) > _MAX_AUDIO_MB:
        raise HTTPException(400, f"Audio too large (max {_MAX_AUDIO_MB}MB)")

    try:
        ctx = json.loads(context) if context else {}
    except json.JSONDecodeError:
        ctx = {}

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
            "transcript": "", "bot_reply": retry_text, "context": ctx, "results": None,
            "audio_base64": base64.b64encode(audio_bytes).decode(), "detected_language": detected_lang,
        }

    assistant = EligibilityAssistant()
    result = await assistant.process_message(transcript, language, ctx)

    try:
        audio_bytes = speak_for_state(result["bot_reply"], force_lang_code=detected_lang)
        audio_b64 = base64.b64encode(audio_bytes).decode()
    except Exception as e:
        logger.warning("Eligibility voice: TTS failed (%s: %s) — returning text only", e.__class__.__name__, e)
        audio_b64 = None

    if result["results"]:
        logger.info("Eligibility voice: results returned (verdict=%s)", result["results"].get("verdict"))

    return {
        "transcript": transcript,
        "bot_reply": result["bot_reply"],
        "context": result["context"],
        "results": result["results"],
        "audio_base64": audio_b64,
        "detected_language": detected_lang,
    }
