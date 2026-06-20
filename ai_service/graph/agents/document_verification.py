"""
document_verification.py — Agent 4 (Document + PPO Verification), the v5.0
upgrade per CLAUDE.md: "NEW: PPO/Aadhaar name-DOB mismatch detection using
Levenshtein string distance. Flags mismatches before they cause pension
rejection."

Scope for this pass: the PPO/Aadhaar mismatch check specifically — the
genuinely new v5.0 capability. The broader Agent 4 responsibilities already
listed in CLAUDE.md before v5.0 (document authenticity, expiry detection,
per-scheme sufficiency check) are the existing ocr_router.py/id_extractor.py
pipeline, reused here rather than rebuilt — this module composes on top of
it, it doesn't replace it.

Zero-retention, matching ocr_router.py's existing design: OCR text is held
only long enough to extract name/dob, then discarded. Only the mismatch
result (score, boolean flags, and the two extracted names/dates themselves —
needed so the citizen can see what didn't match and correct it) is returned.
"""
import gc
import logging

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState
from ai_service.utils.identity_extractor import extract_identity_fields
from ai_service.utils.ppo_matcher import PpoMismatchResult, compute_ppo_mismatch

logger = logging.getLogger(__name__)

_GUIDANCE_REPLY = (
    "Document verification (Aadhaar/PPO mismatch check) ke liye aapko dono documents upload "
    "karne honge — yeh sirf text message se nahi ho sakta. Please /agents/document/verify-ppo "
    "endpoint use karein ya app mein document scanner section mein jaake Aadhaar aur PPO dono "
    "upload karein."
)


async def verify_ppo_aadhaar_match(aadhaar_ocr_text: str, ppo_ocr_text: str) -> dict:
    aadhaar_fields = await extract_identity_fields(aadhaar_ocr_text)
    ppo_fields = await extract_identity_fields(ppo_ocr_text)
    del aadhaar_ocr_text, ppo_ocr_text
    gc.collect()

    if not aadhaar_fields["name"] or not ppo_fields["name"]:
        return {
            "checked": False,
            "reason": "Could not extract a name from one or both documents — OCR quality too low or wrong document type.",
        }

    result: PpoMismatchResult = compute_ppo_mismatch(
        aadhaar_fields["name"], ppo_fields["name"],
        aadhaar_fields.get("dob"), ppo_fields.get("dob"),
    )

    reply = await _compose_reply(aadhaar_fields, ppo_fields, result)

    return {
        "checked": True,
        "name_aadhaar": aadhaar_fields["name"],
        "name_ppo": ppo_fields["name"],
        "dob_aadhaar": aadhaar_fields.get("dob"),
        "dob_ppo": ppo_fields.get("dob"),
        "m_ppo": result.m_ppo,
        "name_mismatch": result.name_mismatch,
        "dob_mismatch": result.dob_mismatch,
        "blocks_dlc_submission": result.name_mismatch or result.dob_mismatch,
        "reply": reply,
    }


async def _compose_reply(aadhaar_fields: dict, ppo_fields: dict, result: PpoMismatchResult) -> str:
    if not result.name_mismatch and not result.dob_mismatch:
        return (
            f"Aapke Aadhaar aur PPO record match kar rahe hain — "
            f"'{aadhaar_fields['name']}' dono jagah sahi hai. DLC submission ke liye ready hain."
        )

    prompt = f"""A citizen's Aadhaar and PPO (Pension Payment Order) records have a mismatch that will block their pension DLC (Digital Life Certificate) submission. Explain this to them in warm, simple Hinglish (2-3 sentences), telling them exactly what differs and that they should get it corrected before submitting.

Aadhaar name: "{aadhaar_fields['name']}" (DOB: {aadhaar_fields.get('dob', 'not found')})
PPO name: "{ppo_fields['name']}" (DOB: {ppo_fields.get('dob', 'not found')})
Name mismatch: {result.name_mismatch} (difference score: {result.m_ppo})
DOB mismatch: {result.dob_mismatch}"""

    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.3)
        return response.content.strip()
    except Exception as e:
        logger.warning("Failed to compose PPO mismatch reply: %s", e)
        return (
            f"Mismatch mila: Aadhaar par '{aadhaar_fields['name']}' aur PPO par '{ppo_fields['name']}'. "
            f"DLC submit karne se pehle ise correct karwa lein."
        )


async def run_document_verify_guidance(state: GraphState) -> GraphState:
    """LangGraph node wrapper for the `document_verify` intent. Unlike
    Agent 1/7/8, real verification (verify_ppo_aadhaar_match) needs OCR'd
    text from two uploaded document images — data a text chat message
    never carries, so this node can't run the actual check. It gives an
    accurate, working-endpoint-pointing reply instead of the stale
    placeholder text that claimed the agent was "still being built" even
    after it was actually finished (see docs/status/AGENTS.md)."""
    state["reply"] = _GUIDANCE_REPLY
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent4_document",
        "tool_called": "none",
        "input": "document_verify intent from text chat",
        "output": "guidance_only",
        "reasoning": "verification requires uploaded document images, not available from a text message",
    })
    return state
