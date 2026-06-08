"""
placeholder.py — honest "not built yet" node for intents that don't have a
real agent behind them yet (application_request, grievance, status_check,
csc_assist, and the injection guard's "blocked" pseudo-intent). Returning a
made-up answer would be worse than saying so plainly.

financial_plan and document_verify used to route here too, but Agent 7 and
Agent 4 are both fully built now — see graph/agents/financial_planning.py's
run_financial_plan_agent and graph/agents/document_verification.py's
run_document_verify_guidance, wired directly in graph/orchestrator.py.
"""
from ai_service.graph.state import GraphState

_NOT_BUILT_YET = {
    "status_check": "Status check abhi Spring Boot gateway se hoga — is service mein abhi available nahi hai.",
}


async def run_placeholder(state: GraphState) -> GraphState:
    intent = state.get("intent", "unknown")
    if intent == "blocked":
        return state  # reply already set by the injection guard
    state["reply"] = _NOT_BUILT_YET.get(
        intent, "Yeh feature abhi Yojna Setu v5.0 rebuild mein build ho raha hai."
    )
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.placeholder",
        "tool_called": "none",
        "input": intent,
        "output": "not_built_yet",
        "reasoning": f"intent '{intent}' has no agent implementation this session",
    })
    return state
