"""
Sarvam AI Integration — Yojna Setu
Provides multilingual support using:
  - Saaras v3     : Speech-to-Text (23 languages incl. 22 Indian + English)
  - Bulbul v3     : Text-to-Speech (35+ voices, pace + temperature params)
  - Mayura        : Translation (Indian languages ↔ English)

NOTE: Saarika v2.5 is DEPRECATED. All STT now uses saaras:v3 with mode=transcribe.
NOTE: Bulbul v3 supports pace + temperature ONLY. Do NOT use pitch or loudness (v2 params).

API Reference: https://docs.sarvam.ai
Get API key: https://dashboard.sarvam.ai
"""
import os
import io
import base64
import logging
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE    = "https://api.sarvam.ai"

# Language codes supported by Sarvam AI
SARVAM_LANGUAGES = {
    "hi": "hi-IN",   # Hindi
    "bn": "bn-IN",   # Bengali
    "ta": "ta-IN",   # Tamil
    "te": "te-IN",   # Telugu
    "kn": "kn-IN",   # Kannada
    "ml": "ml-IN",   # Malayalam
    "mr": "mr-IN",   # Marathi
    "gu": "gu-IN",   # Gujarati
    "pa": "pa-IN",   # Punjabi
    "or": "or-IN",   # Odia
    "en": "en-IN",   # English (Indian accent)
}

# Mapping: user-detected state → best language code
STATE_TO_LANGUAGE = {
    # Hindi belt
    "Uttar Pradesh":  "hi", "Bihar": "hi", "Madhya Pradesh": "hi",
    "Rajasthan": "hi", "Uttarakhand": "hi", "Haryana": "hi",
    "Himachal Pradesh": "hi", "Jharkhand": "hi", "Chhattisgarh": "hi",
    "Delhi": "hi",
    # Regional languages
    "Maharashtra":          "mr",
    "West Bengal":          "bn",
    "Tamil Nadu":           "ta",
    "Andhra Pradesh":       "te",
    "Telangana":            "te",
    "Karnataka":            "kn",
    "Kerala":               "ml",
    "Gujarat":              "gu",
    "Punjab":               "pa",
    "Odisha":               "or",
    # Default to Hindi for others
    "Assam":    "hi", "Tripura": "hi", "Meghalaya": "hi",
    "Manipur":  "hi", "Nagaland": "hi", "Mizoram": "hi",
    "Arunachal Pradesh": "hi", "Sikkim": "hi", "J&K": "hi", "Ladakh": "hi",
    "Goa":      "en",
}

# Bulbul v3 speaker voices — CONFIRMED VALID for bulbul:v3
# Full v3 list: aditya, ritu, ashutosh, priya, neha, rahul, pooja, rohan, simran, kavya,
#               amit, dev, ishita, shreya, ratan, varun, manan, sumit, roopa, kabir,
#               aayan, shubh, advait, amelia, sophia, anand, tanya, tarun, sunny, mani,
#               gokul, vijay, shruti, suhani, mohit, kavitha, rehan, soham, rupali
LANGUAGE_VOICES = {
    "hi-IN": "ritu",      # Female Hindi — warm, clear (confirmed v3)
    "bn-IN": "roopa",     # Bengali female
    "ta-IN": "shruti",    # Tamil female
    "te-IN": "kavitha",   # Telugu female
    "kn-IN": "aditya",    # Kannada male
    "ml-IN": "priya",     # Malayalam female
    "mr-IN": "neha",      # Marathi female
    "gu-IN": "ishita",    # Gujarati female
    "pa-IN": "rohan",     # Punjabi male
    "or-IN": "ritu",      # Odia — fallback to Hindi female
    "en-IN": "amelia",    # English Indian female
}


def get_language_for_state(state: Optional[str]) -> str:
    """Get the best language code for a user's state. Returns 'hi' if unknown."""
    if not state or state == "null":
        return "hi"
    return STATE_TO_LANGUAGE.get(state, "hi")


def get_sarvam_lang_code(lang: Optional[str]) -> str:
    """Convert short lang code to Sarvam format (e.g. 'hi' → 'hi-IN')."""
    if not lang:
        return "unknown"
    return SARVAM_LANGUAGES.get(lang, "unknown")


# ── Audio format conversion helper ───────────────────────────────────────────
# Sarvam saaras:v3 does NOT support webm directly. Convert to wav via ffmpeg.
_SARVAM_SUPPORTED = {"wav", "mp3", "m4a", "ogg", "flac", "aac"}

def _convert_to_wav(audio_bytes: bytes, src_format: str) -> bytes:
    """
    Convert audio bytes from src_format → WAV using ffmpeg (subprocess).
    Returns original bytes if conversion fails (caller will get a Sarvam 400
    and can fall back to Whisper).
    """
    import subprocess, tempfile, os as _os
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{src_format}", delete=False) as src_f:
            src_f.write(audio_bytes)
            src_path = src_f.name
        out_path = src_path.replace(f".{src_format}", ".wav")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1", out_path],
            capture_output=True, timeout=30
        )
        if result.returncode == 0:
            with open(out_path, "rb") as wf:
                return wf.read()
        else:
            logger.warning(f"ffmpeg conversion failed: {result.stderr.decode()[:200]}")
            return audio_bytes
    except FileNotFoundError:
        logger.warning("ffmpeg not found — sending original audio to Sarvam (may fail for webm)")
        return audio_bytes
    except Exception as e:
        logger.warning(f"Audio conversion error: {e}")
        return audio_bytes
    finally:
        for p in [src_path, out_path]:
            try: _os.unlink(p)
            except Exception: pass


# ── Speech to Text (Saaras v3) ───────────────────────────────────────────────
def sarvam_transcribe(
    audio_bytes: bytes,
    audio_format: str = "wav",
    language_code: str = None,     # None = auto-detect
    mode: str = "transcribe",      # transcribe | verbatim | codemix | translit | translate
) -> dict:
    """
    Transcribe audio using Sarvam Saaras v3 (Saarika v2.5 is deprecated).

    Args:
        audio_bytes: Raw audio bytes
        audio_format: 'wav', 'mp3', 'ogg', 'webm', 'm4a', etc.
        language_code: Optional hint e.g. 'hi-IN'. None = auto-detect.
        mode: Transcription mode. Always use 'transcribe' (default) for Yojna Setu.

    Returns:
        {
          "transcript": str,
          "language_code": str,   # detected language
        }
    """
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not set in .env")

    url = f"{SARVAM_BASE}/speech-to-text"
    headers = {"api-subscription-key": SARVAM_API_KEY}

    # webm (recorded by browsers) is NOT supported directly — convert to wav
    fmt = audio_format.lstrip(".").lower()
    if fmt not in _SARVAM_SUPPORTED:
        logger.info(f"Audio format '{fmt}' not supported by Sarvam. Converting to wav via ffmpeg...")
        audio_bytes = _convert_to_wav(audio_bytes, fmt)
        fmt = "wav"

    mime_map = {
        "wav":  "audio/wav",
        "mp3":  "audio/mpeg",
        "m4a":  "audio/x-m4a",
        "ogg":  "audio/ogg",
        "flac": "audio/flac",
        "aac":  "audio/aac",
    }
    mime = mime_map.get(fmt, "audio/wav")

    files = {"file": (f"audio.{fmt}", io.BytesIO(audio_bytes), mime)}

    data = {
        "model": "saaras:v3",       # saarika:v2.5 is deprecated — always use saaras:v3
        "mode": mode,               # always "transcribe" for Yojna Setu
        "with_timestamps": False,
        "with_disfluencies": False,
    }
    # Pass 'unknown' to enable Sarvam auto-detection across 23 languages
    data["language_code"] = language_code if language_code and language_code != "unknown" else "unknown"

    logger.info(f"[SARVAM STT] saaras:v3 | fmt={fmt} | size={len(audio_bytes)}B | lang={data['language_code']} | mode={mode}")
    resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
    if not resp.ok:
        logger.error(f"Sarvam STT {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()
    result = resp.json()

    return {
        "transcript": result.get("transcript", ""),
        "language_code": result.get("language_code", "hi-IN"),
    }


# ── Text to Speech (Bulbul v3) ───────────────────────────────────────────────
def sarvam_tts(
    text: str,
    language_code: str = "hi-IN",
    speaker: str = None,           # Auto-selected from LANGUAGE_VOICES if None
    pace: float = 0.95,            # 0.5 (slow) to 2.0 (fast). 0.95 = natural
    audio_format: str = "mp3",
) -> bytes:
    """
    Convert text to speech using Sarvam Bulbul v3.

    Args:
        text: Text to speak (can be Hindi, Hinglish, or any supported Indian language)
        language_code: 'hi-IN', 'ta-IN', 'bn-IN', etc.
        speaker: Voice name (e.g. 'meera', 'arvind'). Auto-selected if None.
        pace: Speech speed (0.5 slow → 2.0 fast)
        audio_format: 'mp3', 'wav', 'opus', etc.

    Returns:
        Audio bytes (MP3 by default)
    """
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not set in .env")

    url = f"{SARVAM_BASE}/text-to-speech"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json",
    }

    # Auto-select speaker voice for language
    if not speaker:
        speaker = LANGUAGE_VOICES.get(language_code, "meera")

    # Clean text for TTS
    import re
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#{1,6}\s', '', text)
    text = re.sub(r'₹', 'rupay ', text)
    text = re.sub(r'%', ' pratishat ', text)
    text = text.strip()

    payload = {
        "inputs": [text],
        "target_language_code": language_code,
        "speaker": speaker,
        "pace": pace,
        "enable_preprocessing": True,   # handles numbers, dates, etc.
        "model": "bulbul:v3",
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    # Response is a list of base64-encoded audio
    audios = result.get("audios", [])
    if not audios:
        raise ValueError("No audio returned from Sarvam TTS")

    audio_b64 = audios[0]
    return base64.b64decode(audio_b64)


# ── Translation (Mayura) ────────────────────────────────────────────────────
def sarvam_translate(
    text: str,
    source_language: str = "en-IN",
    target_language: str = "hi-IN",
    mode: str = "formal",   # "formal" | "colloquial" | "modern-colloquial"
) -> str:
    """
    Translate text between Indian languages using Sarvam Mayura.

    Args:
        text: Text to translate
        source_language: Source language code ('en-IN', 'hi-IN', etc.)
        target_language: Target language code

    Returns:
        Translated text string
    """
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not set in .env")

    url = f"{SARVAM_BASE}/translate"
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "input": text,
        "source_language_code": source_language,
        "target_language_code": target_language,
        "speaker_gender": "Female",
        "mode": mode,
        "model": "mayura:v1",
        "enable_preprocessing": True,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json().get("translated_text", text)


# ── Convenience function: speak agent question in user's language ─────────────
def speak_for_state(text: str, state: Optional[str] = None, force_lang_code: Optional[str] = None) -> bytes:
    """
    Translate (if needed) and speak text in the appropriate language for the state or forced lang_code.
    Falls back to gTTS if Sarvam key not set.
    """
    if force_lang_code:
        lang_code = force_lang_code
        lang = lang_code.split("-")[0]
    else:
        lang = get_language_for_state(state)
        lang_code = get_sarvam_lang_code(lang)

    if SARVAM_API_KEY:
        try:
            # Translate to regional language if not Hindi
            if lang != "hi" and lang != "en":
                text = sarvam_translate(text, source_language="hi-IN",
                                        target_language=lang_code)
            return sarvam_tts(text, language_code=lang_code)
        except Exception as e:
            logger.warning(f"Sarvam TTS failed ({e}), falling back to gTTS")

    # Fallback to gTTS
    from ai_service.utils.tts import text_to_speech
    return text_to_speech(text, lang=lang)


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    key = SARVAM_API_KEY
    if not key:
        print("⚠️  SARVAM_API_KEY not set — add to ai_service/.env")
        print("   Get free key at: https://dashboard.sarvam.ai")
        print("\n📋 Supported languages by state:")
        for state, lang in list(STATE_TO_LANGUAGE.items())[:10]:
            lc = get_sarvam_lang_code(lang)
            voice = LANGUAGE_VOICES.get(lc, "meera")
            print(f"  {state:25s} → {lang} ({lc}) | voice: {voice}")
        exit(0)

    print("🎙️ Testing Sarvam AI Integration\n" + "="*45)

    # Test TTS
    print("1. Bulbul v3 TTS (Hindi)...")
    audio = sarvam_tts(
        "Namaskar! Main Yojna Sathi hun. Aap kaun se state se hain?",
        language_code="hi-IN"
    )
    with open("/tmp/sarvam_hi.mp3", "wb") as f:
        f.write(audio)
    print(f"   ✅ Hindi MP3: {len(audio)/1024:.1f}KB → /tmp/sarvam_hi.mp3")

    # Test Tamil TTS
    print("2. Bulbul v3 TTS (Tamil)...")
    audio_ta = sarvam_tts(
        "Namaskar! Yojna Sathi ullirundu ungalukkaga aval irukiren.",
        language_code="ta-IN"
    )
    with open("/tmp/sarvam_ta.mp3", "wb") as f:
        f.write(audio_ta)
    print(f"   ✅ Tamil MP3: {len(audio_ta)/1024:.1f}KB → /tmp/sarvam_ta.mp3")

    # Test Translation
    print("3. Mayura Translation (Hindi → Tamil)...")
    translated = sarvam_translate(
        "आपको PM Kisan Samman Nidhi में 6000 रुपये मिलेंगे।",
        source_language="hi-IN",
        target_language="ta-IN"
    )
    print(f"   ✅ Tamil: {translated}")

    print("\n✅ Sarvam AI integration test PASSED!")
