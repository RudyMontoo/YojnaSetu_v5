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
import re
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

# Reasoning models (e.g. Groq's openai/gpt-oss-120b) can emit a stray leading
# token chunk that's just an empty/near-empty JSON object — a tool-call/
# reasoning placeholder artifact, not real content. Sathi's replies are
# always prose, never bare JSON, so this can never be legitimate. Regex
# (not exact-match) to also catch variants like "{ }" or "{}\n".
_EMPTY_JSON_ARTIFACT = re.compile(r"^\{\s*\}$")

from ai_service.graph.orchestrator import get_graph
from ai_service.graph.profile_learner import schedule_profile_learning

logger = logging.getLogger(__name__)


async def _build_initial_state(
    db: AsyncIOMotorDatabase,
    *,
    citizen_id: str,
    session_id: str,
    message: str,
    channel: str,
    lang: str,
    profile: dict | None,
    extra: dict | None = None,
) -> dict:
    existing = await db["conversation_sessions"].find_one({"sessionId": session_id})
    prior_messages = existing["messages"] if existing else []
    return {
        **(extra or {}),
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


async def run_chat_turn(
    db: AsyncIOMotorDatabase,
    *,
    citizen_id: str,
    session_id: str,
    message: str,
    channel: str = "web",
    lang: str = "hi",
    profile: dict | None = None,
    extra_state: dict | None = None,
) -> dict:
    """Runs one full chat turn and persists it. Returns
    {reply, intent, active_schemes, credit_eligibility_results} — session_id
    is the caller's own input, so it isn't echoed back here.

    extra_state seeds additional GraphState keys the caller knows and the
    graph can't derive for itself (e.g. eligibility_flow_active, read from
    the session document) — merged first, so it can never clobber the core
    fields built below."""
    state = await _build_initial_state(
        db, citizen_id=citizen_id, session_id=session_id, message=message,
        channel=channel, lang=lang, profile=profile, extra=extra_state,
    )

    graph = get_graph()
    result = await graph.ainvoke(state)

    return await _persist_turn(
        db, state=state, result=result,
        citizen_id=citizen_id, session_id=session_id,
        channel=channel, lang=lang, profile=profile,
    )


async def stream_chat_turn(
    db: AsyncIOMotorDatabase,
    *,
    citizen_id: str,
    session_id: str,
    message: str,
    channel: str = "web",
    lang: str = "hi",
    profile: dict | None = None,
):
    """Streaming twin of run_chat_turn — an async generator yielding:
        {"type": "token", "text": "..."}   as the composing LLM emits tokens
        {"type": "done", reply, intent, active_schemes}   once, at the end

    Token frames come from LangGraph's stream_mode="messages", which taps
    LLM calls made *inside* graph nodes (langchain-core auto-upgrades
    ainvoke to streaming when a token callback is attached), so no agent
    needed rewriting. The intent classifier's LLM call is filtered out by
    node name — its output is a routing label, not citizen-facing text.

    The "done" frame carries the authoritative reply: if a provider fails
    mid-stream and ainvoke_with_fallback retries on the other provider,
    partial tokens from the failed attempt may have been emitted — clients
    must replace accumulated token text with the done-frame reply.
    """
    state = await _build_initial_state(
        db, citizen_id=citizen_id, session_id=session_id, message=message,
        channel=channel, lang=lang, profile=profile,
    )

    graph = get_graph()
    result = None
    async for mode, chunk in graph.astream(state, stream_mode=["messages", "values"]):
        if mode == "values":
            # Full state after each super-step — the last one is the final state.
            result = chunk
        elif mode == "messages":
            msg_chunk, metadata = chunk
            if metadata.get("langgraph_node") == "intent_classifier":
                continue
            # Real bug fixed 2026-09-04, caught live: node-name filtering alone
            # can't catch extract_profile_facts()'s raw-JSON extraction call —
            # it runs from INSIDE the same "agent1_eligibility" node as the real
            # reply, so its structured output streamed straight into the chat UI
            # as a garbled "{...}" artifact ahead of the actual answer. Internal,
            # non-reply LLM calls tag themselves ["internal"] (see
            # ainvoke_with_fallback's `tags` param) specifically so they can be
            # excluded here regardless of which node they run inside.
            if "internal" in (metadata.get("tags") or []):
                continue
            text = msg_chunk.content
            if isinstance(text, list):  # some providers chunk content as parts
                text = "".join(p if isinstance(p, str) else p.get("text", "") for p in text)
            if text and not _EMPTY_JSON_ARTIFACT.match(text.strip()):
                yield {"type": "token", "text": text}

    if result is None:  # graph produced no values-frame — shouldn't happen, but never persist garbage
        raise RuntimeError("orchestrator graph yielded no final state")

    final = await _persist_turn(
        db, state=state, result=result,
        citizen_id=citizen_id, session_id=session_id,
        channel=channel, lang=lang, profile=profile,
    )
    yield {"type": "done", **final}


async def _persist_turn(
    db: AsyncIOMotorDatabase,
    *,
    state: dict,
    result: dict,
    citizen_id: str,
    session_id: str,
    channel: str,
    lang: str,
    profile: dict | None,
) -> dict:
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

    # Fire-and-forget: learn profile facts from what the citizen just said
    # ("main UP ka kisan hoon, income 1 lakh" should persist, not die with
    # the turn). Runs after the reply is already on its way — zero latency
    # cost, failures logged and swallowed inside the learner.
    #
    # Skipped when Agent 1 already extracted+persisted this turn's facts
    # SYNCHRONOUSLY (agent_outputs["agent1_eligibility"]["profile_learned"] —
    # see eligibility.py's "ask before recommend" redesign): re-running the
    # same extraction here would be a second, redundant LLM call and a
    # second identical Spring PATCH for no benefit.
    already_learned = (
        result.get("agent_outputs", {}).get("agent1_eligibility", {}).get("profile_learned")
    )
    if not already_learned:
        last_user_message = next(
            (m["content"] for m in reversed(state["messages"]) if m["role"] == "user"), ""
        )
        schedule_profile_learning(
            db,
            citizen_id=citizen_id,
            session_id=session_id,
            message=last_user_message,
            intent=result.get("intent", ""),
            current_profile=profile,
        )

    return {
        "reply": reply,
        "intent": result.get("intent", ""),
        "active_schemes": active_schemes,
        # The real EligibilityResponse, when this turn ran the credit
        # eligibility agent — passed straight through for the StartGo UI's
        # results panel. None on every other intent.
        "credit_eligibility_results": (
            result.get("agent_outputs", {}).get("credit_eligibility", {}).get("results")
        ),
        # Tappable answers to the question this reply just asked, and how far
        # through the required questions we are. Empty on every turn that
        # didn't ask a closed question — the UI simply shows no chips then.
        "quick_replies": (
            result.get("agent_outputs", {}).get("credit_eligibility", {}).get("quick_replies") or []
        ),
        "progress": (
            result.get("agent_outputs", {}).get("credit_eligibility", {}).get("progress")
        ),
    }
