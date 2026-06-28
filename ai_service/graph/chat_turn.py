"""
chat_turn.py — the one shared implementation of "process one citizen chat
turn": load prior session messages, run the LangGraph orchestrator, persist
the updated conversation + reasoning traces, return the result.

Extracted from orchestrator_router.py's REST handler so the WebSocket
endpoint (routers/ws_router.py, CLAUDE.md's real target surface for text
chat) runs EXACTLY the same logic — two transports, one behavior. Any chat
semantics change lands here once, not in two places that drift apart.
"""
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.orchestrator import get_graph

logger = logging.getLogger(__name__)


async def run_chat_turn(
    db: AsyncIOMotorDatabase,
    *,
    citizen_id: str,
    session_id: str,
    message: str,
    channel: str = "web",
    lang: str = "hi",
    profile: dict | None = None,
) -> dict:
    """Runs one full chat turn and persists it. Returns
    {reply, intent, active_schemes} — session_id is the caller's own input,
    so it isn't echoed back here."""
    existing = await db["conversation_sessions"].find_one({"sessionId": session_id})
    prior_messages = existing["messages"] if existing else []

    state = {
        "citizen_id": citizen_id,
        "session_id": session_id,
        "channel": channel,
        "lang": lang,
        "profile": profile or {},
        "messages": prior_messages + [{"role": "user", "content": message}],
        "reasoning_trace": [],
        "agent_outputs": {},
        "active_schemes": [],
    }

    graph = get_graph()
    result = await graph.ainvoke(state)

    reply = result.get("reply", "")
    new_messages = state["messages"] + [{"role": "assistant", "content": reply}]

    await db["conversation_sessions"].update_one(
        {"sessionId": session_id},
        {
            "$set": {
                "sessionId": session_id,
                "userId": citizen_id,
                "channel": channel,
                "lang": lang,
                "messages": new_messages,
                "intentTags": [result.get("intent", "")],
                "schemesShown": [s.get("schemeCode") for s in result.get("active_schemes", [])],
            },
            "$setOnInsert": {"startedAt": datetime.now(timezone.utc)},
        },
        upsert=True,
    )

    if result.get("reasoning_trace"):
        for trace in result["reasoning_trace"]:
            trace["session_id"] = session_id
            trace["at"] = datetime.now(timezone.utc)
        await db["reasoning_traces"].insert_many(result["reasoning_trace"])

    # trend_events (CLAUDE.md): every scheme surfaced to a citizen is a "search"
    # event feeding the 7-day trending aggregation. Best-effort — analytics must
    # never break a chat turn.
    active_schemes = result.get("active_schemes", [])
    if active_schemes:
        try:
            now = datetime.now(timezone.utc)
            user_state = (profile or {}).get("state")
            await db["trend_events"].insert_many([
                {
                    "scheme_code": s.get("schemeCode"),
                    "scheme_name": s.get("name"),
                    "event_type": "search",
                    "user_state": user_state,
                    "at": now,
                }
                for s in active_schemes if s.get("schemeCode")
            ])
        except Exception as e:
            logger.warning("trend_events insert failed (non-fatal): %s", e)

    return {
        "reply": reply,
        "intent": result.get("intent", ""),
        "active_schemes": active_schemes,
    }
