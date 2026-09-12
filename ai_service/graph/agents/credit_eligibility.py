"""
credit_eligibility.py — "which NSFDC credit scheme do I actually qualify for?"
as an orchestrator agent, so the StartGo chat can route through the same
13-agent brain as everything else instead of bypassing it.

Distinct from the three neighbouring intents, and the classifier prompt spells
the difference out:
  - eligibility_query  — general welfare-scheme discovery (agent1, vector
                         search over the `schemes` collection; has never known
                         `credit_products` exists)
  - credit_faq         — a named credit scheme's own TERMS (rate, ceiling,
                         moratorium), answered from the catalogue
  - credit_application — they've already chosen a scheme and want to APPLY
  - credit_eligibility — this one: they don't know which scheme fits, and want
                         to be matched against the real eligibility engine

This node is a thin wrapper over services/eligibility_assistant.py, which does
the slot-filling (need / estimatedCost / annualIncome / category / gender) and
then calls Spring's real POST /api/v2/sih/credit/eligibility. Nothing about
the verdict is generated here — routing the StartGo chat through the
orchestrator must not put an LLM back in the path that produces a number a
citizen budgets against. The LLM's only jobs remain extraction of what was
explicitly said, and phrasing the next question.

Multi-turn slot state lives on the conversation_sessions document as
`eligibilityContext` — the same convention application_assistant_router.py
already uses for `applicationContext`, rather than a second session store.
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.state import GraphState
from ai_service.services.eligibility_assistant import EligibilityAssistant

logger = logging.getLogger(__name__)


async def run_credit_eligibility_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    session_id = state.get("session_id") or ""
    lang = state.get("lang") or "en"

    last_user_message = next(
        (m["content"] for m in reversed(state.get("messages") or []) if m.get("role") == "user"), "",
    )

    session = await db["conversation_sessions"].find_one({"sessionId": session_id}) or {}
    context = session.get("eligibilityContext") or {}

    assistant = EligibilityAssistant()
    turn = await assistant.process_message(last_user_message, lang, context)

    # Persisted here rather than in chat_turn's _persist_turn: the slot state
    # is this agent's own concern, and a turn that never reaches this node
    # must not clear it.
    await db["conversation_sessions"].update_one(
        {"sessionId": session_id},
        {"$set": {"sessionId": session_id, "eligibilityContext": turn["context"]}},
        upsert=True,
    )

    results = turn["results"]
    trace = {
        "agent": "credit_eligibility",
        "tool_called": "eligibility_assistant + POST /api/v2/sih/credit/eligibility",
        "slots_filled": sorted(k for k, v in (turn["context"].get("slots") or {}).items() if v is not None),
        "verdict": (results or {}).get("verdict"),
    }

    # active_schemes feeds the "schemes shown this session" record the
    # application assistant later resolves "is scheme ke liye" against, and
    # the trending aggregation — so recommendations surfaced here count the
    # same as ones surfaced by agent 1.
    active_schemes = [
        {"schemeCode": r.get("code"), "name": r.get("name")}
        for r in ((results or {}).get("recommendations") or [])
        if r.get("code")
    ]

    return {
        **state,
        "reply": turn["bot_reply"],
        "active_schemes": active_schemes,
        "reasoning_trace": (state.get("reasoning_trace") or []) + [trace],
        "agent_outputs": {
            **(state.get("agent_outputs") or {}),
            # The real EligibilityResponse, passed through untouched for the
            # UI's results panel — chat_turn surfaces this on its return.
            # quick_replies/progress ride alongside: tappable answers to the
            # question `reply` just asked, so the citizen can answer with a
            # tap instead of typing an amount on a phone keyboard.
            "credit_eligibility": {
                "results": results,
                "quick_replies": turn.get("quick_replies") or [],
                "progress": turn.get("progress"),
            },
        },
    }
