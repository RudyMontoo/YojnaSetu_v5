"""
agent1_eligibility.py — Agent 1 (Eligibility) as a LangGraph node.

Problem 4 redesign: previously this reranked candidates with
`score_eligibility`, a keyword-in-free-text heuristic that never even read
a scheme's structured `eligibilityRules` — and worse, `_profile_from_state`
mapped the citizen's REAL profile fields (annualIncome, category, isBpl,
isDisabled, hasLand, dob — Spring Boot's actual CitizenProfile field names)
onto `UserProfile`'s differently-named dataclass fields (income_lpa,
caste_category, is_bpl, disability, land_acres, age), so every one of those
silently dropped to None on every real chat turn. Only gender/state/district/
occupation happened to share field names and passed through. This means
income, category, BPL, disability, and age — the criteria that matter most —
were never actually used to rank or evaluate eligibility in production.

Fixed here: real criteria-by-criteria comparison (eligibility_rules_engine.py)
against the scheme's actual `eligibilityRules` JSON and the citizen's real
profile field names, no dataclass remapping in between. Retrieval still uses
vector search to narrow candidates (that part was fine); ranking/verdict is
now a genuine rules comparison, not a keyword score.

Path A (citizen has profile data) / Path B (citizen doesn't) per the
redesign: if the top-ranked scheme's verdict is "insufficient_data", the
composed reply explicitly asks for exactly the missing field(s) — profile
data or a Jan-Sahayak Lens document upload — rather than silently guessing.
Never fabricates a criterion a scheme doesn't specify (see
eligibility_rules_engine.py's own docstring for the missing_criteria vs
missing_profile_data distinction).
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.db.vector_search import scheme_vector_search
from ai_service.graph.agents.eligibility_rules_engine import evaluate_eligibility
from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState

logger = logging.getLogger(__name__)

# Human-readable labels for the profile fields we might ask the citizen to fill in.
_FIELD_ASK = {
    "annualIncome": "your annual family income",
    "dob": "your date of birth",
    "category": "your category (general/OBC/SC/ST)",
    "occupation": "your occupation",
    "isBpl": "whether you hold a BPL (below poverty line) card",
    "isRural": "whether you live in a rural or urban area",
    "hasLand": "whether you own agricultural land",
    "state": "which state you're in",
}


def build_query_string(profile: dict) -> str:
    """Builds a retrieval query from the citizen's REAL profile fields (not
    the old UserProfile dataclass, which silently dropped most of them)."""
    parts = []
    if profile.get("occupation"):
        parts.append(profile["occupation"])
    if profile.get("state"):
        parts.append(profile["state"])
    category = (profile.get("category") or "").lower()
    if category and category != "general":
        parts.append(category.upper())
    if profile.get("isBpl"):
        parts.append("BPL below poverty line")
    if profile.get("gender") == "female":
        parts.append("women scheme")
    if profile.get("isDisabled"):
        parts.append("disability handicap")
    if profile.get("isRural"):
        parts.append("rural")
    return " ".join(parts) if parts else ""


async def run_eligibility_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    profile = state.get("profile") or {}
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    query_text = build_query_string(profile) or last_user_message or "government welfare scheme"

    state_filter = profile.get("state") or None
    candidates = await scheme_vector_search(db, query_text, state_filter=state_filter, limit=15)

    evaluated = []
    for s in candidates:
        result = evaluate_eligibility(profile, s)
        s["_eligibility"] = result
        evaluated.append(s)

    # Eligible first, then insufficient-data (still worth showing — might just
    # need one more field), then not-eligible last. Never invents a ranking
    # signal beyond what evaluate_eligibility actually determined.
    verdict_rank = {"eligible": 0, "insufficient_data": 1, "not_eligible": 2}
    evaluated.sort(key=lambda s: verdict_rank.get(s["_eligibility"]["verdict"], 3))
    top = evaluated[:5]

    lines = []
    for s in top:
        e = s["_eligibility"]
        if e["verdict"] == "eligible":
            tag = "ELIGIBLE"
        elif e["verdict"] == "insufficient_data":
            tag = "NEEDS MORE INFO"
        else:
            tag = "NOT ELIGIBLE"
        detail = "; ".join(e["failed"]) if e["failed"] else (
            "missing: " + ", ".join(_FIELD_ASK.get(f, f) for f in e["missing_profile_data"])
            if e["missing_profile_data"] else "criteria matched"
        )
        note = " (this scheme's eligibility data isn't fully available yet)" if e["rules_are_empty"] else ""
        lines.append(f"- {s.get('name')} [{tag}]: {s.get('benefitAmount', '')} — {detail}{note}")
    scheme_summary = "\n".join(lines) or "No matching schemes found."

    # Path B trigger: the single most fixable "insufficient_data" gap across
    # the top schemes, if any — ask for exactly that, don't guess.
    missing_fields: list[str] = []
    for s in top:
        for f in s["_eligibility"]["missing_profile_data"]:
            if f not in missing_fields:
                missing_fields.append(f)
    ask_hint = ""
    if missing_fields:
        asks = ", ".join(_FIELD_ASK.get(f, f) for f in missing_fields[:2])
        ask_hint = (f"\n\nTo confirm eligibility precisely, ask the citizen for: {asks}. "
                    f"They can answer directly, or upload a document via Jan-Sahayak Lens to fill it in "
                    f"automatically. If they can't do either right now, mention they can get help in "
                    f"person at their nearest CSC (Common Service Centre) instead.")

    compose_prompt = f"""You are Sathi, a friendly Hinglish-speaking assistant helping an Indian citizen find government welfare schemes.
Citizen's message: "{last_user_message}"

Matched schemes with REAL eligibility findings (do not contradict or re-guess these — they come from actual comparison against the scheme's criteria and the citizen's profile):
{scheme_summary}{ask_hint}

Write a short, warm reply in Hinglish (3-5 sentences). Be honest and specific: say clearly which schemes they qualify for, which they don't (briefly why), and which need more information (and what, if the hint above names it). Do not invent eligibility criteria not listed above, and do not claim a scheme is "eligible" if it's tagged NOT ELIGIBLE or NEEDS MORE INFO."""

    response = await ainvoke_with_fallback(compose_prompt, temperature=0.4)
    reply = response.content.strip()

    for s in top:
        s.pop("_eligibility", None)  # don't leak the internal keys into GraphState's active_schemes

    state["active_schemes"] = top
    state["reply"] = reply
    state.setdefault("agent_outputs", {})["agent1_eligibility"] = {
        "matched_count": len(top),
        "query_text": query_text,
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent1_eligibility",
        "tool_called": "scheme_vector_search + evaluate_eligibility",
        "input": query_text,
        "output": f"{len(top)} schemes",
        "reasoning": f"state_filter={state_filter}",
    })
    return state
