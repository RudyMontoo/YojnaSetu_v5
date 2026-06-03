"""
Voice Conversation Router — Full Audio Agent
Adds bidirectional voice to the Yojna Sathi agent:

  User speaks → Whisper STT → Agent → gTTS → Audio response

Endpoints:
  POST /voice/conversation/start    → Returns audio: "Namaskar! State batao?"
  POST /voice/conversation/answer   → Accepts audio, returns audio response
  POST /voice/conversation/chat     → One-shot voice chat (no session)
"""
import os
import uuid
import tempfile
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice/conversation", tags=["voice_agent"])

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
MAX_FILE_MB = 25


def safe_header(value: str, max_len: int = 200) -> str:
    """URL-encode non-ASCII chars so they fit in latin-1 HTTP headers."""
    from urllib.parse import quote
    return quote(str(value)[:max_len], safe=" ,|.-_")

# ── Welcome message variants ──────────────────────────────────────────────────
WELCOME_TEXT_HI = (
    "Namaskar! Main Yojna Sathi hun. "
    "Main aapko sarkari yojanaon ki jaankari dunga. "
    "Pehle mujhe batayein aap kaun se state se hain?"
)

SCHEME_INTRO_HI = "Bahut achha! Aapke liye yeh sarkari yojanaen hain: "


# ── Helpers ───────────────────────────────────────────────────────────────────
def _speak(text: str, state: str = None, lang_code: str = None) -> bytes:
    """
    Convert text to audio. Uses Sarvam Bulbul v3 if API key is set,
    else falls back to gTTS. Auto-selects language based on user's state.
    """
    from ai_service.utils.sarvam import speak_for_state, SARVAM_API_KEY
    if SARVAM_API_KEY:
        logger.info(f"TTS via Sarvam Bulbul v3 (state={state}, lang_code={lang_code})")
        return speak_for_state(text, state=state, force_lang_code=lang_code)
    # Fallback
    from ai_service.utils.tts import text_to_speech
    return text_to_speech(text, lang='hi')


async def _transcribe_upload(file: UploadFile, state: str = None, language: str = None) -> tuple[str, str]:
    """
    Transcribe audio. Uses Sarvam Saaras v3 if API key set, else Whisper.
    Returns: (transcript, detected_language_code)
    """
    import os as _os
    suffix = Path(file.filename or "audio.wav").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"Unsupported audio format: {suffix}")
    content = await file.read()
    if len(content) / (1024 * 1024) > MAX_FILE_MB:
        raise HTTPException(400, "Audio too large (max 25MB)")

    from ai_service.utils.sarvam import (
        SARVAM_API_KEY, sarvam_transcribe,
        get_language_for_state, get_sarvam_lang_code, SARVAM_LANGUAGES
    )

    # Resolve language code: explicit > state-derived > auto-detect
    if language:
        lang_code = get_sarvam_lang_code(language)   # e.g. "hi" → "hi-IN"
    elif state and state != "null" and state != "Central":
        lang = get_language_for_state(state)          # e.g. "UP" → "hi"
        lang_code = get_sarvam_lang_code(lang)        # → "hi-IN"
    else:
        lang_code = "unknown" # Enable Sarvam AI auto-detection across 22 languages

    logger.info(f"STT language hint: {lang_code} (state={state}, language={language})")

    if SARVAM_API_KEY and lang_code != "unknown":
        logger.info("STT via Sarvam Saaras v3")
        result = sarvam_transcribe(content, audio_format=suffix.lstrip("."), language_code=lang_code)
        return result["transcript"], lang_code

    # Fallback / Auto-detect: Whisper — naturally handles language auto-detection if state is unknown
    import tempfile, whisper
    whisper_lang = language
    if not whisper_lang and state and state != "null" and state != "Central":
        whisper_lang = get_language_for_state(state)
        
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        model_size = _os.getenv("WHISPER_MODEL", "base")
        model = whisper.load_model(model_size)
        
        params = {
            "initial_prompt": "Hindi-English Hinglish sarkari yojana conversation.",
            "fp16": False
        }
        if whisper_lang:
            params["language"] = whisper_lang
            
        result = model.transcribe(
            tmp_path,
            **params
        )
        detected_w_lang = result.get("language", "hi")
        comp_lang_code = SARVAM_LANGUAGES.get(detected_w_lang, "hi-IN")
        return result["text"].strip(), comp_lang_code
    finally:
        _os.unlink(tmp_path)


def _build_scheme_audio(schemes: list, message: str, state: str = None, lang_code: str = None) -> bytes:
    """Convert scheme list to spoken audio in user's language."""
    parts = [message or SCHEME_INTRO_HI]
    for i, s in enumerate(schemes[:3], 1):  # speak top 3 only
        name = s.get("name", "")
        benefit = s.get("benefit", "")
        score = s.get("eligibility_score", 0)
        parts.append(
            f"Number {i}: {name}. "
            f"Yogyata score {score} pratishat. "
            f"{benefit[:100] if benefit else ''}"
        )
    parts.append(
        "Adhik jaankari ke liye apne CSC kendra ya myscheme.gov.in par jayein. "
        "Dhanyavaad!"
    )
    full_text = " ... ".join(parts)
    return _speak(full_text, state=state, lang_code=lang_code)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/start")
async def voice_start_session():
    """
    Start a new voice agent session.
    Returns MP3 audio of the welcome + first question.
    Also returns the session_id as a response header.
    """
    from ai_service.routers.agent_router import _sessions
    from ai_service.agent.yojna_sathi import UserProfile, get_next_question

    session_id = str(uuid.uuid4())
    profile = UserProfile()
    _sessions[session_id] = {"profile": profile, "question_idx": 0}

    first_q = get_next_question(profile)
    # Speak welcome + first question in Hindi (state not yet known)
    full_text = WELCOME_TEXT_HI + " " + (first_q["question_hi"] or first_q["question_en"])
    audio_bytes = _speak(full_text, state=None)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "X-Session-Id": session_id,
            "X-Question-En": first_q["question_en"],
            "X-Progress": "0",
            "Content-Disposition": "inline; filename=question.mp3",
        }
    )


@router.post("/answer")
async def voice_answer(
    audio: UploadFile = File(..., description="User's spoken answer (WAV/MP3/M4A)"),
    session_id: str = Form(..., description="Session ID from /start"),
    language: Optional[str] = Form(default=None, description="Language hint e.g. 'hi', 'ta'"),
):
    """
    Submit voice answer → get voice response (next question or final schemes).

    Flow:
      1. Whisper transcribes user's audio
      2. Answer is parsed into UserProfile
      3. Agent generates next question OR final scheme list
      4. gTTS converts response to audio
      5. Returns MP3 audio + metadata headers
    """
    from ai_service.routers.agent_router import _sessions, _retrieve_schemes
    from ai_service.agent.yojna_sathi import get_next_question, parse_answer

    session = _sessions.get(session_id)
    if not session:
        # Graceful recovery if server reloaded and wiped memory
        from ai_service.agent.yojna_sathi import UserProfile
        logger.warning(f"Session {session_id} not found. Re-initializing empty profile.")
        profile = UserProfile()
        _sessions[session_id] = {"profile": profile, "question_idx": 0}
        session = _sessions[session_id]

    # Step 1: Get profile (must be before any early returns that reference it)
    profile = session["profile"]

    # Step 2: Transcribe — pass language hint so Sarvam/Whisper don't misdetect
    transcript, detected_lang = await _transcribe_upload(audio, state=profile.state, language=session.get("detected_lang") or language)
    session["detected_lang"] = detected_lang
    logger.info(f"Transcribed: '{transcript}' (lang={detected_lang}, state={profile.state})")

    if not transcript or len(transcript.strip()) < 2:
        repeat_text = "Maafi kijiye, clearly nahi suna. Kripya dobara bolein."
        audio_bytes = _speak(repeat_text, state=profile.state, lang_code=detected_lang)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "X-Session-Id": session_id,
                "X-Transcript": safe_header("(unclear)"),
                "X-Done": "false",
                "X-Progress": "0",
            }
        )

    # Step 2: Parse answer
    current_q = get_next_question(profile)
    if current_q:
        parse_answer(current_q, transcript, profile)

    # Step 3: Get next question
    next_q = get_next_question(profile)
    progress = profile.completion_pct()

    # Step 4a: If done → retrieve schemes and speak results
    if next_q is None or progress >= 100:
        del _sessions[session_id]
        schemes = await _retrieve_schemes(profile)

        message = (
            f"Bahut achha! Aapke profile ke hisaab se "
            f"{len(schemes)} sarkari yojanaen mili hain — "
        )
        audio_bytes = _build_scheme_audio(
            [{"name": s.name, "benefit": s.benefit, "eligibility_score": s.eligibility_score}
             for s in schemes],
            message,
            state=profile.state,
            lang_code=detected_lang,
        )

        scheme_names = " | ".join(s.name for s in schemes[:3])
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "X-Session-Id": session_id,
                "X-Transcript": safe_header(transcript),
                "X-Done": "true",
                "X-Progress": "100",
                "X-Schemes": safe_header(scheme_names),
                "Content-Disposition": "inline; filename=schemes.mp3",
            }
        )

    # Step 4b: Speak next question in user's language
    next_text = next_q.get("question_hi") or next_q["question_en"]
    next_audio = _speak(next_text, state=profile.state, lang_code=detected_lang)

    return Response(
        content=next_audio,
        media_type="audio/mpeg",
        headers={
            "X-Session-Id": session_id,
            "X-Transcript": safe_header(transcript),
            "X-Done": "false",
            "X-Progress": str(progress),
            "X-Question-En": safe_header(next_q["question_en"]),
            "Content-Disposition": "inline; filename=question.mp3",
        }
    )


@router.post("/chat")
async def voice_chat_oneshot(
    audio: UploadFile = File(..., description="User's spoken question (any topic)"),
    state: Optional[str] = Form(default=None),
):
    """
    One-shot voice query (no session needed):
    User asks any question by voice → get spoken scheme recommendations.

    Example: User says "Kya koi housing scheme hai?" → Agent speaks back matching schemes.
    """
    from ai_service.utils.tts import text_to_speech

    # Step 1: Transcribe (Sarvam Saaras v3 or Whisper fallback)
    transcript, detected_lang = await _transcribe_upload(audio, state=state, language=language)

    if not transcript.strip():
        audio_bytes = _speak(
            "Maafi kijiye, aapki awaz clearly nahi aayi. Phir se try karein.",
            state=state, lang_code=detected_lang
        )
        return Response(content=audio_bytes, media_type="audio/mpeg",
                        headers={"X-Transcript": safe_header("(unclear)")})

    # Step 2: RAG retrieval
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        chroma_dir = Path(__file__).parent.parent / "chroma_db"
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction("all-MiniLM-L6-v2")
        col = client.get_collection("yojna_setu_schemes", embedding_function=ef)

        where = {"state": {"$in": [state, "Central"]}} if state else None
        results = col.query(query_texts=[transcript], n_results=3, where=where)

        docs = results["documents"][0]
        metas = results["metadatas"][0]

        # Build spoken response
        spoken_parts = [f"Aapne pucha: {transcript[:80]}. Yeh yojanaen relevant hain:"]
        for i, (doc, meta) in enumerate(zip(docs, metas), 1):
            name = meta.get("name", "")
            benefit_line = next(
                (l.replace("Benefit:", "").strip() for l in doc.split("\n") if l.startswith("Benefit:")),
                ""
            )
            spoken_parts.append(
                f"Number {i}: {name}. {benefit_line[:100] if benefit_line else ''}"
            )
        spoken_parts.append(
            "Aur jaankari ke liye apne nazdiki CSC centre jayein ya "
            "my scheme dot gov dot in visit karein."
        )

        spoken_text = " ... ".join(spoken_parts)

    except Exception as e:
        logger.error(f"RAG error in voice chat: {e}")
        spoken_text = (
            "Maafi kijiye, abhi scheme database se connect nahi ho pa raha. "
            "Kripya myscheme.gov.in par jaayein."
        )

    # Step 3: TTS via Sarvam Bulbul (or gTTS fallback) in user's language
    audio_bytes = _speak(spoken_text, state=state, lang_code=detected_lang)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "X-Transcript": safe_header(transcript),
            "Content-Disposition": "inline; filename=reply.mp3",
        }
    )


@router.get("/test-tts")
async def test_tts(
    text: str = "Namaskar! Main Yojna Sathi hun.",
    state: Optional[str] = None,
):
    """Test TTS in user's state language (Sarvam Bulbul v3 or gTTS fallback)."""
    audio_bytes = _speak(text, state=state)
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=test.mp3"}
    )
