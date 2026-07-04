"""
small_talk.py — node for greetings/thanks/chit-chat ("hello", "namaste",
"who are you"). Exists because the classifier previously had no such label:
"hello" got forced into eligibility_query, vector search returned the 5
nearest schemes to the word "hello" (i.e. random ones, wrong state
included), and the composer presented them as personalized — confidently
wrong. This node answers warmly and invites the citizen to share facts,
but attaches ZERO scheme cards and never claims to have searched anything.
"""
import logging

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)

_PROMPT = """You are Sathi, the friendly assistant of Yojna Setu, which helps Indian citizens discover government welfare schemes they qualify for.

The citizen sent a greeting or casual message (not a scheme question): "{message}"

Reply in 1-2 warm sentences, matching the citizen's language (Hindi/Hinglish/English/regional). Introduce yourself briefly if greeted, and invite them to tell you their state, occupation and yearly income so you can find matching schemes. Do NOT mention, list, or invent any scheme names. Do not claim you searched anything."""

_FALLBACK_REPLY = (
    "Namaste! Main Sathi hoon — sarkari yojnaon ka aapka saathi. "
    "Apna state, kaam aur saalana income bataiye, main aapke liye schemes dhundhta hoon."
)


async def run_small_talk(state: GraphState) -> GraphState:
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    try:
        response = await ainvoke_with_fallback(_PROMPT.format(message=last_user_message), temperature=0.5)
        reply = response.content.strip() or _FALLBACK_REPLY
    except Exception:  # a greeting must never error out — static fallback
        logger.exception("small_talk LLM call failed, using static reply")
        reply = _FALLBACK_REPLY

    state["reply"] = reply
    state["active_schemes"] = []
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.small_talk",
        "tool_called": "none",
        "input": last_user_message[:200],
        "output": "greeting reply, no retrieval",
        "reasoning": "small_talk intent — scheme search deliberately skipped",
    })
    return state
