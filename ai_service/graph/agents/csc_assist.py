"""
csc_assist.py — Agent 9 (CSC Assist), per CLAUDE.md: CSC operators helping
citizens who are missing a required document get concrete, India-realistic
alternatives (e.g. no income certificate → BPL ration card, MGNREGA job
card, gram panchayat certificate...) instead of turning the citizen away.

Endpoint contract (CLAUDE.md): POST /agents/csc/alternatives — Operator JWT
— body: {scheme_id, missing_doc_type}. Implemented with schemeCode as the
identifier, consistent with every other citizen-facing surface in this
codebase (Mongo _ids are internal).

Grounding, not free association: the LLM is given the scheme's REAL
document list and eligibility text from Mongo and asked for alternatives to
one specific document — it is explicitly told to say so when no realistic
alternative exists (e.g. Aadhaar for DBT schemes is legally mandatory, an
alternative would be misinformation that wastes a citizen's trip).
"""
import json
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)

_ALTERNATIVES_PROMPT = """You are helping a CSC (Common Service Centre) operator in India. A citizen wants to apply for this government scheme but is missing one required document.

Scheme: {name}
Ministry: {ministry}
Required documents (from the scheme's official listing): {documents}
Eligibility (official text): "{eligibility_text}"

Missing document: "{missing_doc}"

List realistic alternative documents accepted in Indian government practice for this specific purpose, if any genuinely exist. Be honest: if this document is legally mandatory with no substitute (e.g. Aadhaar for DBT-linked schemes), say so — a false alternative wastes the citizen's time and a trip to the CSC.

Return ONLY a JSON object:
{{
  "has_alternatives": <true|false>,
  "alternatives": [
    {{"document": "<name>", "how_to_get": "<where/how a rural citizen obtains it, 1 sentence>", "note": "<caveat if any, or null>"}}
  ],
  "mandatory_no_substitute": <true if the missing doc is legally required with no alternative>,
  "operator_advice": "<1-2 sentences of practical advice for the CSC operator, in simple Hinglish>"
}}"""


async def suggest_doc_alternatives(db: AsyncIOMotorDatabase, scheme_code: str, missing_doc_type: str) -> dict:
    """Returns {found, scheme_name, ...LLM fields} — `found: False` when the
    schemeCode doesn't exist (caller turns that into a 404)."""
    scheme = await db["schemes"].find_one(
        {"schemeCode": scheme_code},
        {"_id": 0, "name": 1, "ministry": 1, "documents": 1, "eligibilityText": 1},
    )
    if not scheme:
        return {"found": False}

    prompt = _ALTERNATIVES_PROMPT.format(
        name=scheme.get("name", ""),
        ministry=scheme.get("ministry", "") or "not specified",
        documents=", ".join(scheme.get("documents") or []) or "not listed",
        eligibility_text=(scheme.get("eligibilityText") or "")[:1500],
        missing_doc=missing_doc_type,
    )

    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.2)
        raw = response.content.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        parsed = json.loads(raw)
    except Exception as e:
        logger.warning("Agent 9 alternatives extraction failed for %s/%s: %s", scheme_code, missing_doc_type, e)
        return {
            "found": True,
            "scheme_name": scheme.get("name", ""),
            "has_alternatives": False,
            "alternatives": [],
            "mandatory_no_substitute": False,
            "operator_advice": "Suggestion service abhi respond nahi kar raha — scheme ke official portal par document requirements check karein.",
        }

    return {
        "found": True,
        "scheme_name": scheme.get("name", ""),
        "has_alternatives": bool(parsed.get("has_alternatives")),
        "alternatives": parsed.get("alternatives") or [],
        "mandatory_no_substitute": bool(parsed.get("mandatory_no_substitute")),
        "operator_advice": parsed.get("operator_advice") or "",
    }


_CHAT_GUIDANCE = (
    "CSC operator assist (missing-document alternatives) operator dashboard se milta hai — "
    "agar aap CSC operator hain, POST /agents/csc/alternatives endpoint use karein "
    "(scheme code aur missing document type ke saath). Agar aap citizen hain aur koi "
    "document nahi hai, apne najdeeki CSC centre par jayein — /help/csc/nearby se dhundh sakte hain."
)


async def run_csc_assist_guidance(state: GraphState) -> GraphState:
    """Chat-intent node for `csc_assist` — same guidance-only pattern as
    Agent 4's chat node: the real operation needs structured operator input
    (scheme_code + missing_doc_type + operator role), which free-text
    citizen chat doesn't carry. Points at the real surfaces instead of the
    stale 'not built yet' placeholder."""
    state["reply"] = _CHAT_GUIDANCE
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent9_csc",
        "tool_called": "none",
        "input": "csc_assist intent from text chat",
        "output": "guidance_only",
        "reasoning": "CSC assist needs structured operator input (scheme_code, missing_doc_type) + operator role",
    })
    return state
