"""
grievance.py — Agent 5 (Grievance), first slice. Per CLAUDE.md the full
agent navigates pgportal.gov.in via browser-use (120s timeout) — that
automation half is NOT built yet (same honest split as Agent 3: fallback
first, automation composes on top later). What IS real today:

1. A grievance record persisted to the `grievances` collection — citizen's
   complaint, scheme, optional external application id, status "recorded".
   When portal automation lands it picks pending records up from here, so
   nothing filed today is lost.
2. Correct CPGRAMS (pgportal.gov.in) self-filing guidance with
   domain-whitelisted URLs only.

NPCI/SPARSH pension-status monitoring (the v5.0 doc's other Agent 5 duty)
requires institutional API access a solo dev doesn't have — scoped out,
mocked-swappable later, exactly as the rebuild plan flagged.

PII note: complaint text is masked (utils/pii_masker) BEFORE any LLM call,
and the stored record keeps the citizen's original text only in Mongo
(same trust level as conversation_sessions), never in logs.
"""
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.state import GraphState
from ai_service.utils.domain_whitelist import is_allowed_url

logger = logging.getLogger(__name__)

PGPORTAL_URL = "https://pgportal.gov.in"

_GUIDANCE = (
    "Aapki shikayat record ho gayi hai (id: {gid}). Abhi portal par automatic filing "
    "available nahi hai, lekin aap khud 10 minute mein file kar sakte hain:\n"
    "1. {portal} par jayein (CPGRAMS — Government of India ka official grievance portal)\n"
    "2. 'Lodge Public Grievance' par click karke mobile number se register karein\n"
    "3. Ministry/Department chunein{dept_hint}\n"
    "4. Apni complaint likhein — scheme ka naam, application id{app_id_hint}, aur kya problem hai\n"
    "5. Submit ke baad milne wala CPGRAMS registration number sambhal kar rakhein — "
    "status tracking usi se hogi. Jawab aane ki time-limit 30 din hai."
)


async def record_grievance(
    db: AsyncIOMotorDatabase,
    *,
    citizen_id: str,
    complaint_description: str,
    scheme_code: str | None = None,
    external_app_id: str | None = None,
) -> dict:
    """Persists the grievance and returns the guidance reply. Never raises
    on scheme-lookup issues — a grievance about an unknown scheme is still
    a grievance worth recording."""
    scheme_name = None
    if scheme_code:
        scheme = await db["schemes"].find_one({"schemeCode": scheme_code}, {"name": 1})
        scheme_name = scheme.get("name") if scheme else None

    doc = {
        "citizenId": citizen_id,
        "schemeCode": scheme_code,
        "schemeName": scheme_name,
        "externalAppId": external_app_id,
        "complaint": complaint_description,
        "status": "recorded",  # recorded -> filed_on_portal (automation, later) -> resolved
        "statusHistory": [{"status": "recorded", "at": datetime.now(timezone.utc)}],
        "createdAt": datetime.now(timezone.utc),
    }
    result = await db["grievances"].insert_one(doc)
    gid = str(result.inserted_id)

    portal = PGPORTAL_URL if is_allowed_url(PGPORTAL_URL) else "pgportal.gov.in"
    reply = _GUIDANCE.format(
        gid=gid[-8:],  # short suffix — full ObjectId is internal
        portal=portal,
        dept_hint=f" (scheme: {scheme_name})" if scheme_name else "",
        app_id_hint=f" ({external_app_id})" if external_app_id else " (agar hai)",
    )
    logger.info("Agent 5: grievance recorded id=%s scheme=%s", gid, scheme_code)
    return {"grievance_id": gid, "status": "recorded", "scheme_name": scheme_name, "reply": reply}


async def run_grievance_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    """LangGraph node for the `grievance` intent — records the complaint
    from the chat message itself (scheme resolved from active_schemes when
    the citizen was just discussing one)."""
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    active = state.get("active_schemes") or []
    scheme_code = active[0].get("schemeCode") if active else None

    result = await record_grievance(
        db,
        citizen_id=state.get("citizen_id", ""),
        complaint_description=last_user_message,
        scheme_code=scheme_code,
    )

    state["reply"] = result["reply"]
    state.setdefault("agent_outputs", {})["agent5_grievance"] = {
        "grievance_id": result["grievance_id"], "status": result["status"],
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent5_grievance",
        "tool_called": "record_grievance",
        "input": (scheme_code or "no-scheme") + " | " + last_user_message[:80],
        "output": f"recorded {result['grievance_id'][-8:]}",
        "reasoning": "persisted to grievances collection; portal automation pending — self-filing guidance given",
    })
    return state
