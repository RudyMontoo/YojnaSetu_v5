"""
orchestrator.py — the LangGraph StateGraph itself.

Routing follows CLAUDE.md's Orchestrator Routing table:
    START -> intent_classifier -> [route by intent] -> response_composer -> END

Only eligibility_query and comparison have real agents behind them this
session (Agent 1, Agent 8); every other intent (and the injection-guard
"blocked" pseudo-intent) routes to an honest placeholder node rather than a
stub that pretends to work. Widening this is the direct next-session task
per the rebuild plan (Phase 3 onward).
"""
import logging

from langgraph.graph import END, START, StateGraph
from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.agents.application_guidance import run_application_guidance
from ai_service.graph.agents.comparison import run_comparison_agent
from ai_service.graph.agents.csc_assist import run_csc_assist_guidance
from ai_service.graph.agents.document_verification import run_document_verify_guidance
from ai_service.graph.agents.eligibility import run_eligibility_agent
from ai_service.graph.agents.grievance import run_grievance_agent
from ai_service.graph.agents.financial_planning import run_financial_plan_agent
from ai_service.graph.agents.placeholder import run_placeholder
from ai_service.graph.agents.small_talk import run_small_talk
from ai_service.graph.intent_classifier import classify_intent
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)

_INTENT_TO_NODE = {
    "eligibility_query": "agent1_eligibility",
    "comparison": "agent8_comparison",
    "financial_plan": "agent7_financial",
    "document_verify": "agent4_document",
    "csc_assist": "agent9_csc",
    "application_request": "agent3_guidance",
    "grievance": "agent5_grievance",
    "status_check": "placeholder",
    "small_talk": "small_talk",
    "blocked": "placeholder",
}


def _route_by_intent(state: GraphState) -> str:
    return _INTENT_TO_NODE.get(state.get("intent", ""), "placeholder")


def build_graph(db: AsyncIOMotorDatabase):
    """Builds and compiles the Orchestrator graph, bound to a specific Mongo db handle."""

    async def _agent1_node(state: GraphState) -> GraphState:
        return await run_eligibility_agent(state, db)

    async def _agent8_node(state: GraphState) -> GraphState:
        return await run_comparison_agent(state, db)

    async def _agent7_node(state: GraphState) -> GraphState:
        return await run_financial_plan_agent(state, db)

    async def _agent3_node(state: GraphState) -> GraphState:
        return await run_application_guidance(state, db)

    async def _agent5_node(state: GraphState) -> GraphState:
        return await run_grievance_agent(state, db)

    graph = StateGraph(GraphState)
    graph.add_node("intent_classifier", classify_intent)
    graph.add_node("agent1_eligibility", _agent1_node)
    graph.add_node("agent8_comparison", _agent8_node)
    graph.add_node("agent7_financial", _agent7_node)
    graph.add_node("agent3_guidance", _agent3_node)
    graph.add_node("agent4_document", run_document_verify_guidance)
    graph.add_node("agent5_grievance", _agent5_node)
    graph.add_node("agent9_csc", run_csc_assist_guidance)
    graph.add_node("small_talk", run_small_talk)
    graph.add_node("placeholder", run_placeholder)

    graph.add_edge(START, "intent_classifier")
    graph.add_conditional_edges("intent_classifier", _route_by_intent, {
        "agent1_eligibility": "agent1_eligibility",
        "agent8_comparison": "agent8_comparison",
        "agent7_financial": "agent7_financial",
        "agent3_guidance": "agent3_guidance",
        "agent4_document": "agent4_document",
        "agent5_grievance": "agent5_grievance",
        "agent9_csc": "agent9_csc",
        "small_talk": "small_talk",
        "placeholder": "placeholder",
    })
    graph.add_edge("agent1_eligibility", END)
    graph.add_edge("agent8_comparison", END)
    graph.add_edge("agent7_financial", END)
    graph.add_edge("agent3_guidance", END)
    graph.add_edge("agent4_document", END)
    graph.add_edge("agent5_grievance", END)
    graph.add_edge("agent9_csc", END)
    graph.add_edge("small_talk", END)
    graph.add_edge("placeholder", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    """Singleton compiled graph, built lazily against the shared Mongo db handle."""
    global _compiled_graph
    if _compiled_graph is None:
        from ai_service.db.mongo import get_db
        _compiled_graph = build_graph(get_db())
    return _compiled_graph
