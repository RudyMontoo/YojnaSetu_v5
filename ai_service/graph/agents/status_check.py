"""
status_check.py — the `status_check` intent's real node.

Per CLAUDE.md's Orchestrator Routing table this intent was the last one still
pointing at the honest placeholder ("Status check abhi Spring Boot gateway se
hoga"). That was correct as a stopgap — application records ARE owned by the
Spring Boot side — but a citizen asking "meri application ka kya status hai?"
in chat deserves a real grounded answer, not a redirect.

ai_service and Spring Boot share the same Mongo database (yojnasetu), and the
`applications` collection is Spring's own (model: Application.java —
userId/schemeCode/schemeName/status/statusHistory/appliedAt). This node reads
it directly, read-only, filtered to the caller's own userId (== GraphState's
citizen_id, both the JWT `sub`), and composes a grounded status summary. It
NEVER writes applications — creating/mutating an application stays a Spring
Boot REST concern (POST/PATCH /api/v2/applications), this is a read-only view
surfaced through chat.

Grounding rule: the reply is built deterministically from the real rows first
(so it works with zero LLM budget and can't hallucinate a status that isn't in
the data); an optional LLM pass only rephrases that same factual summary into
warmer Hinglish, with a plain fallback to the deterministic text on any error.
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)

MAX_APPLICATIONS = 15  # a citizen with more than this is an edge case; bound the reply length

# Machine status -> citizen-facing Hinglish. Kept exhaustive against
# Application.java's documented status set (saved|in_progress|submitted|
# approved|rejected|disbursed); an unknown value falls back to itself.
_STATUS_HINGLISH = {
    "saved": "save ki hui hai (abhi apply nahi hua)",
    "in_progress": "chal rahi hai (process mein hai)",
    "submitted": "submit ho chuki hai — jawab ka intezaar hai",
    "approved": "approve ho gayi hai 🎉",
    "rejected": "reject ho gayi hai",
    "disbursed": "paisa aapke account mein aa chuka hai ✅",
}


def _status_line(app: dict) -> str:
    name = app.get("schemeName") or app.get("schemeCode") or "ek scheme"
    raw = (app.get("status") or "saved").lower()
    phrase = _STATUS_HINGLISH.get(raw, raw)
    line = f"• {name}: {phrase}"
    if app.get("externalAppId"):
        line += f" (ref: {app['externalAppId']})"
    return line


def _compose_deterministic(apps: list[dict]) -> str:
    if not apps:
        return (
            "Aapne abhi tak koi application save ya submit nahi ki hai. "
            "Jab aap kisi scheme ko save karke apply karenge, uska status yahan dikhega. "
            "Kisi scheme ke liye eligibility check karni ho toh mujhe apni details bata dein."
        )
    lines = [_status_line(a) for a in apps]
    header = (
        f"Aapki {len(apps)} application" + ("s" if len(apps) != 1 else "") + " ka status:"
    )
    return header + "\n" + "\n".join(lines)


async def build_status_summary(citizen_id: str, db: AsyncIOMotorDatabase) -> dict:
    """Reads the caller's own application rows (read-only) and returns a
    grounded status summary. Never raises on an empty/unknown citizen — an
    absence of applications is itself a valid, answerable state."""
    apps: list[dict] = []
    if citizen_id:
        cursor = (
            db["applications"]
            .find(
                {"userId": citizen_id},
                {
                    "schemeName": 1,
                    "schemeCode": 1,
                    "status": 1,
                    "externalAppId": 1,
                    "appliedAt": 1,
                    "lastStatusCheck": 1,
                },
            )
            .sort("appliedAt", -1)
            .limit(MAX_APPLICATIONS)
        )
        apps = await cursor.to_list(length=MAX_APPLICATIONS)

    deterministic = _compose_deterministic(apps)
    return {
        "application_count": len(apps),
        "applications": apps,
        "reply": deterministic,  # the grounded, LLM-independent text
    }


async def _polish(deterministic: str, count: int) -> str:
    """Optional warmth pass. Strictly rephrases the already-grounded summary —
    the prompt forbids inventing any status not present in the text. Falls back
    to the deterministic summary on any LLM error or empty response."""
    if count == 0:
        return deterministic  # the no-applications text is already friendly; don't spend an LLM call
    prompt = (
        "Neeche ek citizen ki government scheme applications ka factual status summary hai. "
        "Ise ek short, warm Hinglish message mein dobara likho (2-3 lines). "
        "IMPORTANT: koi bhi naya status ya scheme mat jodo — sirf jo neeche diya hai wahi rephrase karo. "
        "Agar koi application 'reject' hui hai toh usey CPGRAMS grievance file karne ka gentle suggestion de sakte ho.\n\n"
        f"Factual summary:\n{deterministic}"
    )
    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.3)
        text = (response.content or "").strip()
        return text or deterministic
    except Exception as e:  # noqa: BLE001 — any LLM failure must degrade to the grounded text
        logger.warning("status_check polish failed, using deterministic summary: %s", e)
        return deterministic


async def run_status_check_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    """LangGraph node for the `status_check` intent. Replaces the placeholder
    that redirected the citizen to 'the Spring Boot gateway'."""
    citizen_id = state.get("citizen_id", "")
    result = await build_status_summary(citizen_id, db)
    result["reply"] = await _polish(result["reply"], result["application_count"])

    state["reply"] = result["reply"]
    state.setdefault("agent_outputs", {})["status_check"] = {
        "application_count": result["application_count"],
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.status_check",
        "tool_called": "build_status_summary",
        "input": citizen_id or "no_citizen_id",
        "output": f"{result['application_count']} applications",
        "reasoning": "read-only applications lookup by userId, grounded reply",
    })
    return state
