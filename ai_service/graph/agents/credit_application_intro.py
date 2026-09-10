"""
credit_application_intro.py — the orchestrator's ONLY job for the
`credit_application` intent: recognize "I want to apply" and hand off to the
dedicated application-assistant flow, in the citizen's selected language.

The real slot-filling/summarize/confirm logic lives entirely in
ai_service/services/application_assistant.py, reached via its own router
(/application-assistant/chat) — not through this node. That's a deliberate
split, not a shortcut: the orchestrator's single-turn WS/REST contract
(ChatResponse: reply, intent, active_schemes) has no field for a structured
payload, and bolting one on would touch chat_turn.py, ws_router.py, and
orchestrator_router.py's response model for a flow that's naturally
multi-turn and stateful in its own right. So this node only detects the
INTENT and opens the door; the frontend sees intent == "credit_application"
in this turn's response and switches to calling applyChat() for every turn
after, until a structured_payload closes the loop (see ChatPage.jsx).
"""
from ai_service.graph.llm import ainvoke_with_fallback, language_instruction
from ai_service.graph.state import GraphState

_PROMPT = """You are the SC Concessional Credit Assistant. The citizen just said they \
want to apply for a scheme: "{message}"

Write a short, warm reply (1-2 sentences) confirming you'll help them start the \
application, and that you'll ask a couple of quick questions. Do not ask any \
question yourself — that happens next. {language_hint}"""

_FALLBACK_REPLIES = {
    "en": "Sure — let's start your application. I'll just need a couple of quick details.",
    "hi": "Bilkul — chaliye aapka application shuru karte hain. Bas kuch details chahiye honge.",
}
_DEFAULT_FALLBACK_LANG = "hi"


async def run_credit_application_intro(state: GraphState) -> GraphState:
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    lang = (state.get("lang") or "").strip().lower()
    fallback_reply = _FALLBACK_REPLIES.get(lang, _FALLBACK_REPLIES[_DEFAULT_FALLBACK_LANG])

    try:
        response = await ainvoke_with_fallback(
            _PROMPT.format(message=last_user_message, language_hint=language_instruction(lang)),
            temperature=0.3,
        )
        reply = response.content.strip() or fallback_reply
    except Exception:
        reply = fallback_reply

    state["reply"] = reply
    state["active_schemes"] = []
    state.setdefault("agent_outputs", {})["credit_application_intro"] = {"handed_off": True}
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.credit_application_intro",
        "tool_called": "none",
        "input": last_user_message[:200],
        "output": "handed off to /application-assistant/chat",
        "reasoning": "credit_application intent — real slot-filling happens in the dedicated flow",
    })
    return state
