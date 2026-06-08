"""
agent1_eligibility.py — Agent 1 (Eligibility) as a LangGraph node.

Ports the interview/profile logic that already existed in
ai_service/agent/yojna_sathi.py (UserProfile, score_eligibility) rather than
reinventing it — that logic was the strongest existing asset per the
codebase survey. What's new here: candidate retrieval now comes from
MongoDB Atlas Vector Search (via db.vector_search) instead of ChromaDB, and
the final reply is composed by Gemini instead of returned as a raw list.

This is a full ReAct tool-loop in the v5.0 doc's spec ("6-tool ReAct
agent"); this first-session version is a single retrieve-then-rerank pass,
which is enough to prove the Orchestrator -> Mongo -> reply path end-to-end.
Widening to the full ReAct tool set is later Phase 3 work.
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.agent.yojna_sathi import UserProfile, score_eligibility
from ai_service.db.vector_search import scheme_vector_search
from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)


def _profile_from_state(state: GraphState) -> UserProfile:
    raw = state.get("profile") or {}
    known_fields = set(UserProfile.__dataclass_fields__.keys())
    filtered = {k: v for k, v in raw.items() if k in known_fields}
    return UserProfile(**filtered)


def _scheme_blob(scheme: dict) -> str:
    return " ".join([
        scheme.get("name", ""),
        scheme.get("eligibilityText", ""),
        scheme.get("benefitAmount", ""),
        " ".join(scheme.get("category", [])),
        scheme.get("state") or "",
    ])


async def run_eligibility_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    profile = _profile_from_state(state)
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    query_text = profile.to_query_string()
    if query_text == "government welfare scheme" and last_user_message:
        # Profile is empty/thin — fall back to the raw message as the retrieval query
        query_text = last_user_message

    state_filter = profile.state if profile.state else None
    candidates = await scheme_vector_search(db, query_text, state_filter=state_filter, limit=15)

    ranked = sorted(
        candidates,
        key=lambda s: score_eligibility(_scheme_blob(s), profile),
        reverse=True,
    )
    top = ranked[:5]
    for s in top:
        s["eligibilityScore"] = score_eligibility(_scheme_blob(s), profile)

    scheme_summary = "\n".join(
        f"- {s['name']}: {s.get('benefitAmount', '')} (eligibility score: {s['eligibilityScore']}/100)"
        for s in top
    ) or "No matching schemes found."

    compose_prompt = f"""You are Sathi, a friendly Hinglish-speaking assistant helping an Indian citizen find government welfare schemes.
Citizen's message: "{last_user_message}"
Known profile: {profile.to_query_string()}

Matched schemes (already ranked by eligibility):
{scheme_summary}

Write a short, warm reply in Hinglish (2-4 sentences) presenting these schemes. Mention the top 2-3 by name and benefit. If the profile is thin, gently ask one clarifying question (e.g. state, income, occupation) to improve future matches. Do not invent schemes not listed above."""

    response = await ainvoke_with_fallback(compose_prompt, temperature=0.4)
    reply = response.content.strip()

    state["active_schemes"] = top
    state["reply"] = reply
    state.setdefault("agent_outputs", {})["agent1_eligibility"] = {
        "matched_count": len(top),
        "query_text": query_text,
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent1_eligibility",
        "tool_called": "scheme_vector_search",
        "input": query_text,
        "output": f"{len(top)} schemes",
        "reasoning": f"state_filter={state_filter}",
    })
    return state
