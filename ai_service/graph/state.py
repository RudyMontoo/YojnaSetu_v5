"""
state.py — GraphState shared by the Orchestrator and every agent node.

Field names and shape follow CLAUDE.md's GraphState dataclass exactly:
"never rename fields without updating all agents." This file is the one
place that contract lives in code; every agent module should import
GraphState from here rather than redefining its own shape.
"""
from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    citizen_id: str
    session_id: str
    channel: str            # "web" | "voice" | "whatsapp"
    lang: str
    profile: dict            # CitizenProfile decrypted
    messages: list[dict]      # conversation history: [{"role": "user"|"assistant", "content": str}]
    intent: str              # set by intent_classifier
    active_schemes: list[dict]  # set by Agent 1 / Agent 8
    reasoning_trace: list[dict]  # append-only, every agent writes here
    agent_outputs: dict       # keyed by agent name
    reply: str                # final composed response text
