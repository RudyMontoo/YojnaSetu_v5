"""
agent8_comparison.py — Agent 8 (Scheme Comparison) as a LangGraph node.

Per CLAUDE.md: "LangGraph + Gemini Flash + Atlas Vector Search — side-by-side
scheme comparison against citizen profile, plain-language recommendation."
This first-session version retrieves 2 candidate schemes via the same
vector_search module Agent 1 uses (the two most relevant to the citizen's
message), then asks Gemini for a structured plain-language comparison. It
does not yet parse "compare X vs Y" out of the message to look up specific
named schemes — that's a small, obvious follow-up, not done here to keep
this session's scope to proving the graph wiring end-to-end.
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.db.vector_search import scheme_vector_search
from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)


async def run_comparison_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    profile = state.get("profile") or {}
    state_filter = profile.get("state")

    candidates = await scheme_vector_search(db, last_user_message, state_filter=state_filter, limit=2)

    if len(candidates) < 2:
        state["reply"] = "Maaf kijiye, compare karne ke liye kam se kam 2 schemes chahiye — thoda aur batayein kaunsi schemes compare karni hain."
        state["active_schemes"] = candidates
        return state

    a, b = candidates[0], candidates[1]
    prompt = f"""Compare these two Indian government welfare schemes for a citizen, in Hinglish, in under 120 words.
Scheme A: {a['name']} — Benefit: {a.get('benefitAmount', '')} — Eligibility: {a.get('eligibilityText', '')}
Scheme B: {b['name']} — Benefit: {b.get('benefitAmount', '')} — Eligibility: {b.get('eligibilityText', '')}

Citizen's message: "{last_user_message}"

Give a short side-by-side comparison and end with one clear recommendation sentence."""

    response = await ainvoke_with_fallback(prompt, temperature=0.3)
    reply = response.content.strip()

    state["active_schemes"] = candidates
    state["reply"] = reply
    state.setdefault("agent_outputs", {})["agent8_comparison"] = {
        "scheme_a": a["name"],
        "scheme_b": b["name"],
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent8_comparison",
        "tool_called": "scheme_vector_search",
        "input": last_user_message[:200],
        "output": f"{a['name']} vs {b['name']}",
        "reasoning": "top-2 vector search results used as comparison candidates",
    })
    return state
