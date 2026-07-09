"""
placeholder.py — honest fallback node for intents with no real agent behind
them. As of the status_check wiring, the ONLY live route here is the injection
guard's "blocked" pseudo-intent (whose reply is already set); it also catches
any unknown/future intent the classifier might emit before its agent exists.

Everything that used to land here now has a real node: financial_plan (Agent
7), document_verify (Agent 4), and status_check (graph/agents/status_check.py's
run_status_check_agent — reads the citizen's own applications and returns a
grounded status summary instead of redirecting to "the Spring Boot gateway").
"""
from ai_service.graph.state import GraphState


async def run_placeholder(state: GraphState) -> GraphState:
    intent = state.get("intent", "unknown")
    if intent == "blocked":
        return state  # reply already set by the injection guard
    state["reply"] = "Yeh feature abhi Yojna Setu v5.0 rebuild mein build ho raha hai."
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "orchestrator.placeholder",
        "tool_called": "none",
        "input": intent,
        "output": "not_built_yet",
        "reasoning": f"intent '{intent}' has no agent implementation this session",
    })
    return state
