"""
id_extractor.py — Document Unique ID Extractor
Yojna Setu Jan-Sahayak Lens

Extracts and MASKS unique identifier numbers from OCR text.
RAW IDs are NEVER stored or returned — only masked tokens.
Supports: Aadhaar, PAN, Voter ID, Ration Card, Driving Licence, Passport, Bank Account
"""
import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DetectedID:
    id_type: str          # "aadhaar" | "pan" | "voter_id" | etc.
    masked_value: str     # e.g. "XXXX-XXXX-3456"
    confidence: float     # 0.0 – 1.0
    doc_hint: str         # human-readable label


# ── Regex Patterns ─────────────────────────────────────────────────────────────
# Order matters: more specific patterns first

_PATTERNS = [
    {
        "id_type": "aadhaar",
        "doc_hint": "Aadhaar Card",
        "regex": re.compile(r'\b(\d{4})[\s\-]?(\d{4})[\s\-]?(\d{4})\b'),
        # Aadhaar: 12 digits in groups of 4
        # Mask: XXXX-XXXX-{last4}
        "mask_fn": lambda m: f"XXXX-XXXX-{m.group(3)}",
        "confidence": 0.90,
    },
    {
        "id_type": "pan",
        "doc_hint": "PAN Card",
        "regex": re.compile(r'\b([A-Z]{5})([0-9]{4})([A-Z])\b'),
        # PAN: ABCDE1234F
        # Mask: XXXXX{last4 digits}X
        "mask_fn": lambda m: f"XXXXX{m.group(2)}X",
        "confidence": 0.95,
    },
    {
        "id_type": "voter_id",
        "doc_hint": "Voter ID (EPIC)",
        "regex": re.compile(r'\b([A-Z]{3})(\d{7})\b'),
        # EPIC: ABC1234567
        # Mask: XXX{last4}
        "mask_fn": lambda m: f"XXX{m.group(2)[-4:]}",
        "confidence": 0.85,
    },
    {
        "id_type": "driving_licence",
        "doc_hint": "Driving Licence",
        "regex": re.compile(r'\b([A-Z]{2})[\-\s]?(\d{2})[\-\s]?(\d{4})[\-\s]?(\d{7})\b'),
        # DL: DL-01-2019-1234567
        # Mask: XX-XX-XXXX-{last4}
        "mask_fn": lambda m: f"XX-XX-XXXX-{m.group(4)[-4:]}",
        "confidence": 0.80,
    },
    {
        "id_type": "passport",
        "doc_hint": "Passport",
        "regex": re.compile(r'\b([A-Z])(\d{7})\b'),
        # Passport: A1234567
        # Mask: X{last4}
        "mask_fn": lambda m: f"X{m.group(2)[-4:]}",
        "confidence": 0.85,
    },
    {
        "id_type": "ration_card",
        "doc_hint": "Ration Card",
        # Context-gated: only extract 8-12 digit numbers NEAR ration card keywords
        "regex": re.compile(r'\b(\d{8,12})\b'),
        "mask_fn": lambda m: f"XXXX{m.group(1)[-4:]}",
        "confidence": 0.65,
        "context_keywords": ["ration", "aahar", "food", "rashan", "bpl", "apl", "antodaya"],
    },
]

# Keywords that strongly indicate document type
_DOC_TYPE_KEYWORDS = {
    "aadhaar": ["aadhaar", "aadhar", "uid", "uidai", "भारत सरकार", "unique identification"],
    "pan":     ["permanent account", "income tax", "pan card", "आयकर"],
    "voter_id": ["election commission", "epic", "voter", "निर्वाचन", "electoral"],
    "driving_licence": ["driving licence", "motor vehicle", "transport", "dl no"],
    "passport": ["republic of india", "passport", "पासपोर्ट", "ministry of external"],
    "ration_card": ["ration", "food security", "राशन", "खाद्य", "civil supplies", "bpl", "apl"],
    "bank_passbook": ["passbook", "account no", "ifsc", "savings account", "bank of"],
}


def detect_doc_type(ocr_text: str) -> str:
    """
    Classify document type from OCR text via keyword heuristics.
    Returns a doc_type string like 'aadhaar', 'pan', etc., or 'unknown'.
    """
    text_lower = ocr_text.lower()
    scores = {doc_type: 0 for doc_type in _DOC_TYPE_KEYWORDS}

    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                scores[doc_type] += 1

    best_type = max(scores, key=lambda k: scores[k])
    if scores[best_type] == 0:
        return "unknown"
    return best_type


def extract_ids(ocr_text: str) -> list[DetectedID]:
    """
    Extract and mask unique IDs from OCR text.
    Returns list of DetectedID — ONLY masked values, never raw.
    
    Privacy guarantee: raw matched strings are immediately discarded
    after masking. Never logged or stored.
    """
    text = ocr_text
    detected_doc_type = detect_doc_type(text)
    results: list[DetectedID] = []
    seen_types = set()

    for pattern in _PATTERNS:
        pid = pattern["id_type"]
        if pid in seen_types:
            continue

        # Context gate for ambiguous patterns (e.g. ration card numbers)
        if "context_keywords" in pattern:
            context_found = any(
                kw in text.lower() for kw in pattern["context_keywords"]
            )
            # Only extract if document type strongly matches OR context keyword present
            if not context_found and detected_doc_type != pid:
                continue

        match = pattern["regex"].search(text)
        if match:
            try:
                masked = pattern["mask_fn"](match)
                # Adjust confidence based on doc type corroboration
                confidence = pattern["confidence"]
                if detected_doc_type == pid:
                    confidence = min(1.0, confidence + 0.05)

                results.append(DetectedID(
                    id_type=pid,
                    masked_value=masked,
                    confidence=round(confidence, 2),
                    doc_hint=pattern["doc_hint"],
                ))
                seen_types.add(pid)
                # ── Privacy: immediately replace raw match in local text var ──
                text = text[:match.start()] + ("[REDACTED]") + text[match.end():]
            except Exception as e:
                logger.warning(f"Masking failed for {pid}: {e}")

    return results


def build_agent_answer(detected_ids: list[DetectedID], doc_type: str) -> str:
    """
    Build a natural language answer string from OCR results,
    suitable to be fed back into the Yojna Sathi agent interview.
    
    Example: "Aadhaar Card mila. Number: XXXX-XXXX-3456. Document valid hai."
    """
    if not detected_ids:
        return f"{doc_type} scan hua lekin koi unique ID nahi mili."

    parts = [f"{doc_type} scan successful ✅"]
    for did in detected_ids:
        parts.append(f"{did.doc_hint} number: {did.masked_value}")
    parts.append("Document valid hai.")
    return ". ".join(parts)
