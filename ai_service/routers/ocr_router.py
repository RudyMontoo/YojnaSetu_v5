"""
ocr_router.py — Jan-Sahayak Lens OCR Endpoint
Yojna Setu AI Service

POST /ocr/scan — Zero-retention document scanner.
Accepts image (JPEG/PNG/WEBP) or PDF via multipart/form-data.
Processes in volatile RAM, returns masked IDs. Nothing written to disk.

Two usage modes:
  1. Standalone scan  — no session_id → returns result to frontend
  2. In-chat scan     — with session_id → also feeds result into agent interview
"""
import gc
import logging
import time
from typing import Optional, Annotated

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ai_service.utils.doc_scanner import preprocess_image, pdf_page_to_image_bytes
from ai_service.utils.id_extractor import extract_ids, detect_doc_type, build_agent_answer
from ai_service.utils.auth import require_api_key
from ai_service.utils.rate_limiter import ocr_limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ocr"])

# ── Response Models ────────────────────────────────────────────────────────────

class DetectedIDOut(BaseModel):
    id_type: str
    masked_value: str
    confidence: float
    doc_hint: str

class ScanResponse(BaseModel):
    doc_type: str
    detected_ids: list[DetectedIDOut]
    validity: dict
    fed_to_agent: bool = False
    agent_message: Optional[str] = None
    page_count: int = 1

# ── Supported MIME types ───────────────────────────────────────────────────────
_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
_PDF_MIME    = "application/pdf"


# ── Main Endpoint ─────────────────────────────────────────────────────────────
@router.post("/scan", response_model=ScanResponse, dependencies=[Depends(require_api_key)])
async def scan_document(
    request: Request,
    file: Annotated[UploadFile, File(description="Document image (JPEG/PNG/WEBP) or PDF")],
    session_id: Annotated[Optional[str], Form()] = None,
):
    """
    Scan a government document and extract unique ID numbers (masked).

    - Processes entirely in RAM — zero disk writes, zero storage.
    - Returns masked IDs (e.g. XXXX-XXXX-3456) — raw IDs never returned.
    - If session_id is provided, automatically feeds result into active
      Yojna Sathi interview session as the next answer.
    """
    image_bytes: Optional[bytes] = None
    all_ocr_text = ""
    page_count = 1

    # ── Rate limiting (shared ocr_limiter, 10 req/min per IP) ────────────────
    ocr_limiter.check(ocr_limiter.get_client_ip(request))

    try:
        # ── Read file into memory ──────────────────────────────────────────────
        raw_bytes = await file.read()
        content_type = file.content_type or ""

        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Empty file received.")
        if len(raw_bytes) > 20 * 1024 * 1024:  # 20MB limit
            raise HTTPException(status_code=413, detail="File too large. Max 20MB.")

        # ── PDF handling ───────────────────────────────────────────────────────
        if content_type == _PDF_MIME or file.filename.lower().endswith(".pdf"):
            try:
                page_images = pdf_page_to_image_bytes(raw_bytes)
                page_count = len(page_images)
            except ImportError:
                raise HTTPException(
                    status_code=422,
                    detail="PDF support requires pdf2image + poppler. Contact admin."
                )
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))

            # OCR all pages, concatenate text
            for page_bytes in page_images:
                page_text = await _run_ocr(page_bytes)
                all_ocr_text += " " + page_text

            del page_images  # free memory immediately
            del raw_bytes

        elif content_type in _IMAGE_MIMES or any(
            file.filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]
        ):
            image_bytes = raw_bytes
            del raw_bytes
            all_ocr_text = await _run_ocr(image_bytes)
            del image_bytes

        else:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type: {content_type}. Use JPEG, PNG, WEBP, or PDF."
            )

        # ── Extract IDs from OCR text ──────────────────────────────────────────
        detected_ids = extract_ids(all_ocr_text)
        doc_type_key = detect_doc_type(all_ocr_text)
        doc_type_label = _doc_type_label(doc_type_key)

        # ── Validity check ─────────────────────────────────────────────────────
        validity = _assess_validity(all_ocr_text, detected_ids)

        # ── Free OCR text from memory (contains raw text) ──────────────────────
        del all_ocr_text
        gc.collect()

        # ── If session_id given: feed result into agent interview ──────────────
        fed_to_agent = False
        agent_message = None

        if session_id:
            fed_to_agent, agent_message = await _feed_to_agent(
                session_id, detected_ids, doc_type_label
            )

        response = ScanResponse(
            doc_type=doc_type_label,
            detected_ids=[
                DetectedIDOut(
                    id_type=d.id_type,
                    masked_value=d.masked_value,
                    confidence=d.confidence,
                    doc_hint=d.doc_hint,
                )
                for d in detected_ids
            ],
            validity=validity,
            fed_to_agent=fed_to_agent,
            agent_message=agent_message,
            page_count=page_count,
        )

        del detected_ids
        gc.collect()

        return JSONResponse(
            content=response.model_dump(),
            headers={
                "X-No-Store": "true",
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR scan error: {type(e).__name__}: {e}", exc_info=False)
        raise HTTPException(status_code=500, detail="Document processing failed. Please try a clearer image.")
    finally:
        # Belt-and-suspenders: clear any remaining refs
        image_bytes = None
        all_ocr_text = ""
        gc.collect()


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _run_ocr(image_bytes: bytes) -> str:
    """
    Preprocess image with OpenCV, then run EasyOCR.
    Returns raw OCR text string. image_bytes freed by caller.
    """
    preprocessed = None
    try:
        # OpenCV preprocessing
        preprocessed = preprocess_image(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    text = ""
    try:
        # ── Primary: EasyOCR (stable, no oneDNN crashes) ──────────────────────
        reader = _get_easyocr()
        # readtext returns list of (bbox, text, confidence)
        results = reader.readtext(preprocessed)

        lines = []
        for item in results:
            # item = (bbox, text, confidence)
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                text_val, conf = item[1], item[2]
                if conf > 0.3:
                    lines.append(str(text_val))

        text = " ".join(lines)

    except Exception as e:
        logger.warning(
            f"EasyOCR failed ({type(e).__name__}: {e}), falling back to tesseract"
        )
        text = await _run_tesseract_fallback(preprocessed)

    finally:
        del preprocessed

    if not text.strip():
        raise HTTPException(
            status_code=500,
            detail="OCR engine could not read the document. Please try a clearer image."
        )
    return text


# ── EasyOCR singleton (load model once per process) ───────────────────────────
_easyocr_instance = None

def _get_easyocr():
    """
    Returns a cached EasyOCR Reader.
    Supports English and Hindi (covers most Indian government documents).
    GPU is disabled to avoid VRAM pressure on the development machine.
    """
    global _easyocr_instance
    if _easyocr_instance is None:
        import easyocr
        _easyocr_instance = easyocr.Reader(
            ["en"],      # English; add "hi" for Hindi if needed
            gpu=False,   # keeps it stable on machines with limited VRAM
            verbose=False,
        )
    return _easyocr_instance


async def _run_tesseract_fallback(image_array) -> str:
    """Tesseract fallback if EasyOCR also fails. image_array is a numpy ndarray."""
    if image_array is None:
        return ""
    try:
        import pytesseract
        text = pytesseract.image_to_string(image_array, config="--oem 3 --psm 6")
        return text
    except ImportError:
        logger.warning("Tesseract fallback unavailable: pytesseract not installed")
        return ""
    except Exception as e:
        logger.warning(f"Tesseract fallback failed: {e}")
        return ""


def _assess_validity(ocr_text: str, detected_ids) -> dict:
    """
    Heuristic validity check based on OCR keywords and ID detection confidence.
    """
    text_lower = ocr_text.lower()
    has_seal_keywords = any(kw in text_lower for kw in [
        "government of india", "भारत सरकार", "election commission",
        "income tax department", "unique identification", "ministry",
        "uidai", "state government"
    ])
    has_expiry = any(kw in text_lower for kw in ["valid", "expiry", "expires", "validity"])
    high_conf_ids = [d for d in detected_ids if d.confidence >= 0.80]
    is_valid = len(high_conf_ids) > 0 or has_seal_keywords

    return {
        "is_valid": is_valid,
        "has_official_seal": has_seal_keywords,
        "has_expiry_info": has_expiry,
        "confidence": round(
            sum(d.confidence for d in detected_ids) / len(detected_ids)
            if detected_ids else 0.0,
            2
        ),
    }


def _doc_type_label(doc_type_key: str) -> str:
    labels = {
        "aadhaar":         "Aadhaar Card",
        "pan":             "PAN Card",
        "voter_id":        "Voter ID Card",
        "driving_licence": "Driving Licence",
        "passport":        "Passport",
        "ration_card":     "Ration Card",
        "bank_passbook":   "Bank Passbook",
        "unknown":         "Government Document",
    }
    return labels.get(doc_type_key, "Government Document")


async def _feed_to_agent(
    session_id: str,
    detected_ids,
    doc_type_label: str,
) -> tuple[bool, Optional[str]]:
    """
    If an active agent session exists, inject the OCR result as the next answer.
    This lets the agent continue the interview automatically after a doc scan.
    """
    try:
        from ai_service.routers.agent_router import _sessions, get_next_question_for_session
        from ai_service.agent.yojna_sathi import parse_answer

        session = _sessions.get(session_id)
        if not session:
            return False, None

        profile = session["profile"]
        current_q = get_next_question_for_session(profile)

        if current_q:
            # Build a natural language answer from the OCR result
            answer_text = build_agent_answer(detected_ids, doc_type_label)
            parse_answer(current_q, answer_text, profile)
            agent_msg = f"✅ {doc_type_label} scan kiya gaya. Interview continue ho raha hai..."
            return True, agent_msg

    except Exception as e:
        logger.warning(f"Agent feed failed (non-fatal): {e}")

    return False, None
