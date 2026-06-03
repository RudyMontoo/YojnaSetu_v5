"""
TTS (Text-to-Speech) Module — Yojna Setu
Converts text to audio using gTTS (Hindi/English/Hinglish)

- Hindi text → gTTS with lang='hi' (best quality)
- Hinglish mixed → gTTS with lang='hi' (handles transliterated words)
- Returns MP3 bytes (can be streamed or saved)
"""
import io
import re
import logging
from gtts import gTTS

logger = logging.getLogger(__name__)

# Language detection helpers
HINDI_CHAR_PATTERN = re.compile(r'[\u0900-\u097F]')  # Devanagari Unicode range

def detect_lang(text: str) -> str:
    """
    Detect if text is mostly Hindi (Devanagari) or Hinglish (Latin).
    Returns 'hi' for Hindi, 'hi' for Hinglish (gTTS handle mixed best with 'hi').
    """
    devanagari_chars = len(HINDI_CHAR_PATTERN.findall(text))
    total_alpha = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return 'hi'
    ratio = devanagari_chars / total_alpha
    # If more than 20% Devanagari → use Hindi TTS
    return 'hi' if ratio > 0.2 else 'hi'  # always 'hi' works best for Hinglish


def text_to_speech(text: str, lang: str = None, slow: bool = False) -> bytes:
    """
    Convert text to MP3 audio bytes.

    Args:
        text: Text to convert (Hindi, English, or Hinglish)
        lang: Language code ('hi' for Hindi, 'en' for English). Auto-detected if None.
        slow: Speak slowly (useful for clarity in rural settings)

    Returns:
        MP3 audio bytes
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty for TTS")

    # Clean text — remove markdown, emoji, special chars that confuse TTS
    clean = re.sub(r'\*+', '', text)       # Remove bold/italic asterisks
    clean = re.sub(r'#{1,6}\s', '', clean)  # Remove markdown headers
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)  # Links → just text
    clean = re.sub(r'₹', 'rupay ', clean)  # ₹ → spoken word
    clean = re.sub(r'%', ' pratishat ', clean)  # % → spoken
    clean = clean.strip()

    if not lang:
        lang = detect_lang(clean)

    logger.info(f"TTS: lang={lang}, chars={len(clean)}")

    buf = io.BytesIO()
    tts = gTTS(text=clean, lang=lang, slow=slow)
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


def question_to_audio(question_en: str, question_hi: str = None,
                      prefer_hindi: bool = True) -> bytes:
    """
    Convert an agent question to audio.
    Prefers Hindi version if available and prefer_hindi=True.
    """
    if prefer_hindi and question_hi:
        return text_to_speech(question_hi, lang='hi')
    return text_to_speech(question_en, lang='hi')  # gTTS handles Hinglish


# ── Test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os

    test_cases = [
        ("Namaskar! Main Yojna Sathi hun. Aap kaun se state se hain?", "hi"),
        ("आपकी श्रेणी क्या है? SC, ST, OBC, या General?", "hi"),
        ("Bahut achha! Maharashtra ke liye 5 sarkari yojanaen mili hain.", "hi"),
        ("Pradhan Mantri Kisan Samman Nidhi mein rupay 6000 pratishat saal milte hain.", "hi"),
    ]

    print("🎙️ TTS Test\n" + "="*40)
    for i, (text, lang) in enumerate(test_cases):
        audio_bytes = text_to_speech(text, lang=lang)
        out_path = f"/tmp/tts_test_{i}.mp3"
        with open(out_path, "wb") as f:
            f.write(audio_bytes)
        size_kb = len(audio_bytes) / 1024
        print(f"  [{i+1}] {text[:50]}...")
        print(f"       → {size_kb:.1f}KB MP3 saved: {out_path}")

    print("\n✅ TTS test passed — MP3 files generated in /tmp/")
