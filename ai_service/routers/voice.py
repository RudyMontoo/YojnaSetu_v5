"""
Whisper Voice Pipeline — Phase 5 of Yojna Setu AI Service
/transcribe endpoint: accepts audio file → returns Hinglish text

Supports: .wav, .mp3, .m4a, .ogg, .webm
Uses OpenAI Whisper (local, no API key needed)
"""
import os
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from ai_service.utils.auth import require_api_key
from ai_service.utils.rate_limiter import voice_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

# Whisper model — 'base' for fastest, 'small' for better accuracy
# 'medium' for best quality (uses ~2GB VRAM — feasible on RTX 4050 6GB)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")

# Lazy-loaded whisper model
_whisper_model = None

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
MAX_FILE_SIZE_MB = 25


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}...")
        _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
        logger.info("Whisper model loaded ✅")
    return _whisper_model


# ── Response Models ────────────────────────────────────────────────────────────
class TranscribeResponse(BaseModel):
    text: str                       # detected text (Hinglish)
    language: str                   # detected language code
    confidence: float               # 0-1 confidence score
    duration_seconds: float         # audio duration
    word_count: int


class VoiceToSchemeResponse(BaseModel):
    transcript: str
    language: str
    chat_reply: Optional[str] = None
    matched_schemes: Optional[list[dict]] = None


# ── Routes ─────────────────────────────────────────────────────────────────────
@router.post("/transcribe", response_model=TranscribeResponse, dependencies=[Depends(require_api_key)])
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    language: Optional[str] = Form(default=None),  # hint: "hi" for Hindi
):
    """
    Transcribe uploaded audio to text using Whisper.
    Optimized for Hinglish (Hindi-English code-switching).
    """
    voice_limiter.check(voice_limiter.get_client_ip(request))
    # Validate file extension
    suffix = Path(file.filename or "audio.wav").suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise HTTPException(400, f"Unsupported format: {suffix}. Use: {SUPPORTED_FORMATS}")

    # Validate file size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large ({size_mb:.1f}MB). Max {MAX_FILE_SIZE_MB}MB.")

    # Write to temp file for Whisper
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        model = get_whisper_model()

        # Transcribe — for Hindi/Hinglish: set language="hi" or let auto-detect
        options = {
            "task": "transcribe",
            "language": language,                    # None = auto-detect
            "initial_prompt": (                      # guides model towards Hinglish
                "Yeh ek Hindi-English mix conversation hai about government schemes. "
                "सरकारी योजनाओं के बारे में बात हो रही है।"
            ),
            "fp16": False,  # Use fp32 for CPU
        }

        result = model.transcribe(tmp_path, **options)

        text = result["text"].strip()
        detected_lang = result.get("language", "unknown")

        # Calculate confidence from log probs
        segments = result.get("segments", [])
        if segments:
            avg_logprob = sum(s.get("avg_logprob", -1) for s in segments) / len(segments)
            confidence = max(0.0, min(1.0, (avg_logprob + 1) / 1))  # rough normalization
            duration = segments[-1].get("end", 0)
        else:
            confidence = 0.0
            duration = 0.0

        return TranscribeResponse(
            text=text,
            language=detected_lang,
            confidence=round(confidence, 2),
            duration_seconds=round(duration, 1),
            word_count=len(text.split()),
        )

    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(500, f"Transcription failed: {str(e)}")
    finally:
        os.unlink(tmp_path)


@router.post("/query", response_model=VoiceToSchemeResponse, dependencies=[Depends(require_api_key)])
async def voice_to_scheme(
    request: Request,
    file: UploadFile = File(...),
    state: Optional[str] = Form(default=None),
    language: Optional[str] = Form(default=None),
):
    """
    End-to-end voice query:
    audio → Whisper STT → text → RAG chain → Hinglish scheme reply
    """
    voice_limiter.check(voice_limiter.get_client_ip(request))
    # Step 1: Transcribe
    transcribe_resp = await transcribe_audio(request, file, language)
    transcript = transcribe_resp.text

    if not transcript or len(transcript.strip()) < 3:
        return VoiceToSchemeResponse(
            transcript="(audio unclear)",
            language=transcribe_resp.language,
            chat_reply="Maafi kijiye, audio clearly nahi suna. Phir se try karein.",
        )

    # Step 2: Send transcript to RAG chat chain
    try:
        from ai_service.rag_chain import build_rag_chain, get_retriever
        import chromadb
        from chromadb.utils import embedding_functions
        from pathlib import Path as P

        chain = build_rag_chain()
        filters = {}
        if state:
            filters = {"state": {"$in": [state, "Central"]}}

        reply = chain.invoke({
            "question": transcript,
            "filters": filters if filters else None,
        })

        # Also get structured scheme metadata
        chroma_dir = P(__file__).parent.parent / "chroma_db"
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        col = client.get_collection("yojna_setu_schemes", embedding_function=ef)
        results = col.query(
            query_texts=[transcript],
            n_results=3,
            where={"state": {"$in": [state, "Central"]}} if state else None,
        )

        matched = []
        for meta in (results.get("metadatas") or [[]])[0]:
            matched.append({
                "name": meta.get("name", ""),
                "sector": meta.get("sector", ""),
                "state": meta.get("state", "Central"),
                "apply_url": meta.get("apply_url", ""),
            })

        return VoiceToSchemeResponse(
            transcript=transcript,
            language=transcribe_resp.language,
            chat_reply=reply,
            matched_schemes=matched,
        )

    except Exception as e:
        logger.warning(f"RAG chain error after transcription: {e}")
        # Still return the transcript even if RAG fails
        return VoiceToSchemeResponse(
            transcript=transcript,
            language=transcribe_resp.language,
            chat_reply=None,
        )


@router.get("/models")
async def list_models():
    """List available Whisper models and their sizes."""
    return {
        "available_models": {
            "tiny":   {"size": "39M params", "vram": "~1GB", "speed": "fastest"},
            "base":   {"size": "74M params", "vram": "~1GB", "speed": "fast", "current": WHISPER_MODEL_SIZE == "base"},
            "small":  {"size": "244M params", "vram": "~2GB", "speed": "moderate"},
            "medium": {"size": "769M params", "vram": "~5GB", "speed": "slow", "note": "Best for RTX 4050 6GB"},
            "large":  {"size": "1500M params", "vram": "~10GB", "speed": "slowest"},
        },
        "current_model": WHISPER_MODEL_SIZE,
        "set_via": "WHISPER_MODEL env var",
    }
