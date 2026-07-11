"""
vision_ocr.py — high-accuracy, ANY-language document extraction via a local
vision LLM (Ollama on GPU), replacing the EasyOCR→regex chain for the primary
path.

Why this beats traditional OCR for Indian government documents:
- A vision model reads ANY script (Devanagari, Tamil, Telugu, Bengali,
  Gujarati, Kannada, Malayalam, Odia, Gurmukhi, Urdu, …) with NO per-language
  config — the old EasyOCR reader was English-only and silently dropped every
  non-Latin character.
- It extracts STRUCTURED fields directly from the image (docType/name/dob/
  idNumber), instead of OCR'ing to noisy text and regex-hunting — one misread
  digit no longer breaks the whole extraction.
- It runs LOCALLY on the GPU (Ollama): free, no quota, and — critically for
  DPDP — the Aadhaar image NEVER leaves the machine (a cloud vision API would
  ship a citizen's ID photo to a third party).

Design: light-touch preprocessing (perspective-correct + upscale, keep the
NATURAL image — vision models are trained on real photos, so binary
thresholding hurts them), then one structured-JSON call to the vision model,
then validation (Aadhaar Verhoeff checksum). Never raises — the caller falls
back to the EasyOCR path if the vision model is unavailable.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re

import cv2
import httpx
import numpy as np

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
# granite3.2-vision fits a 6 GB GPU (~4s/scan warm) and extracts structured
# fields accurately across doc types. qwen2.5vl:3b reads native scripts a touch
# better but needs ~10 GB → CPU-bound (~52s) on a laptop GPU — set
# OCR_VISION_MODEL=qwen2.5vl:3b to opt into it where VRAM allows.
VISION_MODEL = os.getenv("OCR_VISION_MODEL", "granite3.2-vision")
_TIMEOUT = 120.0  # first call loads the model into VRAM — allow for it

_EXTRACT_PROMPT = (
    "You are reading a photo of an Indian government identity document "
    "(Aadhaar card, PAN card, income/caste certificate, PPO, ration card, etc.). "
    "The text may be in ANY Indian language/script or English, or a mix. "
    "Read it carefully and return ONLY a JSON object with these keys:\n"
    '  "doc_type": one of ["aadhaar","pan","income_certificate","caste_certificate",'
    '"ppo","ration_card","voter_id","driving_license","other"],\n'
    '  "name": the person\'s full name EXACTLY as printed (do not translate or transliterate), or null,\n'
    '  "dob": date of birth as printed (keep the original format), or null,\n'
    '  "id_number": the main ID/document number with spaces removed, or null,\n'
    '  "gender": "male"/"female"/"other"/null,\n'
    '  "address": full address as printed, or null,\n'
    '  "languages_detected": list of language names you see on the document,\n'
    '  "raw_text": all visible text, preserving the original scripts.\n'
    "Do not guess or hallucinate any field that is not clearly visible — use null. "
    "Return only the JSON, nothing else."
)


def vision_model_available() -> bool:
    """True only if the Ollama daemon is up AND the vision model is pulled."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=4.0)
        r.raise_for_status()
        names = {m.get("name", "") for m in r.json().get("models", [])}
        # match with or without an explicit :tag
        base = VISION_MODEL.split(":")[0]
        return any(n == VISION_MODEL or n.split(":")[0] == base for n in names)
    except Exception:
        return False


def preprocess_for_vision(image_bytes: bytes, *, max_side: int = 1600) -> bytes:
    """Light-touch cleanup that HELPS a vision model: perspective-correct the
    document if we can find its 4 corners, then ensure a reasonable resolution.
    Keeps the natural (color) image — NO binary thresholding. Returns JPEG bytes.
    Falls back to the original bytes on any failure."""
    try:
        from ai_service.utils.doc_scanner import deskew, detect_document_contour

        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes

        warped = detect_document_contour(img)  # 4-corner perspective transform, or None
        if warped is not None and warped.size > 0:
            img = warped
        img = deskew(img)

        h, w = img.shape[:2]
        longest = max(h, w)
        if longest < 900:                      # upscale tiny phone crops
            scale = 900 / longest
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        elif longest > max_side:               # cap huge images (keeps the call fast)
            scale = max_side / longest
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return buf.tobytes() if ok else image_bytes
    except Exception as e:  # noqa: BLE001 — preprocessing must never break the scan
        logger.info("vision preprocess fell back to raw bytes: %s", e)
        return image_bytes


async def extract_document_fields(image_bytes: bytes) -> dict | None:
    """Runs the vision model on a document image and returns structured fields,
    or None if the model is unavailable / the call fails (caller then falls back
    to EasyOCR). Adds `aadhaar_checksum_valid` when an Aadhaar number is read."""
    if not vision_model_available():
        return None

    prepared = preprocess_for_vision(image_bytes)
    b64 = base64.b64encode(prepared).decode("ascii")
    payload = {
        "model": VISION_MODEL,
        "prompt": _EXTRACT_PROMPT,
        "images": [b64],
        "stream": False,
        "format": "json",        # force valid JSON out
        "options": {"temperature": 0},
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "")
        fields = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning("vision OCR failed (%s: %s) — caller will fall back", e.__class__.__name__, e)
        return None

    _correct_doc_type(fields)
    # Validate any 12-digit number with the Aadhaar checksum — catches OCR
    # misreads and helps confirm it really is an Aadhaar.
    idn = (fields.get("id_number") or "").replace(" ", "")
    if idn.isdigit() and len(idn) == 12:
        fields["aadhaar_checksum_valid"] = verhoeff_validate(idn)
    fields["engine"] = f"vision:{VISION_MODEL}"
    return fields


# PAN = 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
# Keyword → doc_type, checked against raw_text (any script). Order matters.
_DOCTYPE_KEYWORDS = [
    ("aadhaar", ("aadhaar", "aadhar", "आधार", "uidai", "ஆதார்", "ఆధార్", "আধার")),
    ("pan", ("permanent account number", "income tax department", "पैन")),
    ("income_certificate", ("income certificate", "आय प्रमाण", "annual income", "வருமான")),
    ("caste_certificate", ("caste certificate", "जाति प्रमाण", "scheduled caste", "scheduled tribe", "obc certificate")),
    ("ration_card", ("ration card", "राशन", "bpl", "below poverty line", "public distribution")),
    ("voter_id", ("election commission", "voter", "epic", "मतदाता")),
    ("driving_license", ("driving licence", "driving license", "transport department")),
]


def _correct_doc_type(fields: dict) -> None:
    """Small models sometimes misclassify (e.g. Aadhaar → 'pan'). Correct it
    from the strongest signals: a Verhoeff-valid 12-digit number is almost
    certainly Aadhaar; otherwise fall back to keyword evidence in the raw text.
    Only overrides when there's a clear signal — never blanks a good guess."""
    idn = (fields.get("id_number") or "").replace(" ", "")
    blob = " ".join(str(fields.get(k, "")) for k in ("raw_text", "doc_type")).lower()

    # Strongest signal: a checksum-valid 12-digit number == Aadhaar.
    if idn.isdigit() and len(idn) == 12 and verhoeff_validate(idn):
        fields["doc_type"] = "aadhaar"
        return
    if _PAN_RE.match(idn.upper()):
        fields["doc_type"] = "pan"
        return
    for doc_type, kws in _DOCTYPE_KEYWORDS:
        if any(kw in blob for kw in kws):
            fields["doc_type"] = doc_type
            return


# ── Aadhaar Verhoeff checksum (the real algorithm UIDAI uses) ──────────────────
_VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]


def verhoeff_validate(number: str) -> bool:
    """True if the 12-digit string passes the Verhoeff checksum every real
    Aadhaar number satisfies. A random/misread 12-digit number will fail."""
    if not number.isdigit():
        return False
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(digit)]]
    return c == 0
