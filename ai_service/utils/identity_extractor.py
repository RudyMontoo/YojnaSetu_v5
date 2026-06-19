"""
identity_extractor.py — extracts name + DOB from OCR'd document text, for
Agent 4's PPO/Aadhaar mismatch check (ppo_matcher.py needs the two names to
compare; nothing in the existing OCR pipeline extracts names today —
utils/id_extractor.py only extracts and masks ID *numbers*, by design).

Security: per CLAUDE.md's L4 LLM security layer ("PII masker before every
Gemini call"), the OCR text is run through pii_masker.mask_pii() before it
ever reaches an LLM — Aadhaar/PAN/phone/email number patterns are redacted
first. Names are NOT PII-masker targets (mask_pii only targets ID-number
shaped strings), so they remain visible to the model, which is required for
this to work at all. Raw OCR text is never persisted — only the extracted
name/dob strings the caller explicitly asks for.
"""
import json
import logging

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.utils.pii_masker import mask_pii

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """Extract the person's full name and date of birth from this Indian government document OCR text. The text may be noisy (OCR errors, mixed languages, stray characters).

OCR text: "{text}"

Return ONLY a JSON object: {{"name": "<full name as printed, or null if not found>", "dob": "<date of birth as printed, or null if not found>"}}
Do not translate or reformat the name. Do not guess if not clearly present."""


async def extract_identity_fields(ocr_text: str) -> dict:
    """Returns {"name": str|None, "dob": str|None}. Never raises — returns
    both-None on any failure so callers can degrade gracefully rather than
    crash a document-verification flow over a flaky LLM call."""
    masked_text, pii_found = mask_pii(ocr_text)
    if pii_found:
        logger.info("PII masked before identity extraction: %s", pii_found)

    prompt = _EXTRACT_PROMPT.format(text=masked_text[:2000])
    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.0)
        raw = response.content.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        parsed = json.loads(raw)
        return {"name": parsed.get("name") or None, "dob": parsed.get("dob") or None}
    except Exception as e:
        logger.warning("Identity extraction failed: %s: %s", e.__class__.__name__, e)
        return {"name": None, "dob": None}
