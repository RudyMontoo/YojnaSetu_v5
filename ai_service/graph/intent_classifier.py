"""
intent_classifier.py — the Orchestrator's entry node.

Classifies the citizen's message into one of the intents from CLAUDE.md's
routing table, then the graph's conditional edges dispatch to the matching
agent node. Only "eligibility_query" and "comparison" have real agents
behind them this session (Agent 1, Agent 8) — everything else routes to an
honest "not built yet" placeholder rather than silently mishandling it.
"""
import json
import logging

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState
from ai_service.utils.injection_guard import check_injection
from ai_service.utils.pii_masker import mask_pii

logger = logging.getLogger(__name__)

INTENTS = [
    "eligibility_query",
    "application_request",
    "grievance",
    "comparison",
    "financial_plan",
    "document_verify",
    "status_check",
    "csc_assist",
    "small_talk",
]

_CLASSIFY_PROMPT = """You are an intent classifier for Yojna Setu, an Indian government welfare scheme assistant.
Classify the citizen's message into exactly one of these intents:
- eligibility_query: asking what schemes they qualify for, or describing their situation to find schemes
- application_request: wants help applying/filling a form for a specific scheme
- grievance: complaint about a rejected/stuck/missing payment or application
- comparison: comparing two or more specific schemes against each other
- financial_plan: wants total benefit calculation across all schemes they qualify for
- document_verify: uploading or asking about a document (Aadhaar, income cert, etc.)
- status_check: checking status of an application they already submitted
- csc_assist: a CSC operator asking for help on behalf of a citizen
- small_talk: greeting (hello/namaste/hi), thanks, goodbye, "who are you / what can you do", or chit-chat with NO facts about their situation and NO scheme question

Only pick eligibility_query if the message actually asks about schemes or gives situation facts (state, occupation, income, age, etc.). A bare greeting is small_talk, never eligibility_query.

Message (may be in Hindi, Hinglish, or English): "{message}"

Respond with ONLY a JSON object: {{"intent": "<one of the labels above>"}}"""


async def classify_intent(state: GraphState) -> GraphState:
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    sanitized, blocked, reason = check_injection(last_user_message)
    if blocked:
        logger.warning("Injection guard blocked message: %s", reason)
        state["intent"] = "blocked"
        state["reply"] = "Maaf kijiye, aapka message process nahi ho saka. Kripya dobara try karein."
        return state

    masked, pii_found = mask_pii(sanitized)
    if pii_found:
        logger.info("PII masked before LLM call: %s", pii_found)

    prompt = _CLASSIFY_PROMPT.format(message=masked)
    response = await ainvoke_with_fallback(prompt, temperature=0.0)
    raw = response.content.strip()

    intent = "eligibility_query"  # safe default — most messages are implicitly eligibility queries
    try:
        cleaned = raw.strip("`").removeprefix("json").strip()
        parsed = json.loads(cleaned)
        candidate = parsed.get("intent", "")
        if candidate in INTENTS:
            intent = candidate
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Intent classifier returned non-JSON, defaulting to eligibility_query: %r", raw)

    state["intent"] = intent
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.intent_classifier",
        "tool_called": "llm_classify",
        "input": masked[:500],
        "output": intent,
        "reasoning": raw[:500],
    })
    return state
