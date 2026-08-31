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

"Ask before recommending" redesign (2026-08-31): a broad query ("give me
pension scheme") against a thin profile used to go straight to a wall of
results tagged NEEDS MORE INFO for almost everything — technically honest,
but not what a citizen wants from a first message. Now:
  1. Facts stated in THIS message are extracted and merged in immediately
     (via profile_learner.extract_profile_facts) — previously that only
     happened fire-and-forget AFTER the reply, so stating your age/state/
     income in your very first message never actually helped that message's
     own results.
  2. If a field is missing for a MAJORITY of the top candidates (not just
     one scheme's idiosyncratic ask), that's treated as "the query is too
     broad to rank meaningfully yet" — the reply asks for those 2-4 fields
     instead of dumping results. If profile data is already sufficient
     (nothing missing for most candidates), it goes straight to results —
     never re-asks what's already known.
  3. Which fields get asked is 100% derived from evaluate_eligibility's real
     per-scheme missing_profile_data — never a hardcoded per-category
     question list. A scheme category whose real criteria aren't in
     eligibilityRules at all (this engine only knows maxIncome/minAge/
     maxAge/category/occupation/isRural/isBpl/hasLand/state — nothing else)
     simply never triggers a question about anything else; there is no
     "existing pension coverage" or "student's class" field in this data
     model, and this code does not invent one.
"""
import logging
from collections import Counter

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.db.vector_search import scheme_vector_search
from ai_service.graph.agents.eligibility_rules_engine import evaluate_eligibility
from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.profile_learner import extract_profile_facts
from ai_service.graph.state import GraphState
from ai_service.utils.spring_client import patch_citizen_profile

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


def compute_systemic_gaps(missing_counts: Counter, top_count: int) -> list[str]:
    """A field missing for a MAJORITY of the top candidates means the
    profile is too thin to rank this query meaningfully — not just one
    scheme's idiosyncratic requirement. Returns fields ranked most-missing
    first; empty if no field clears the majority bar (or there are no
    candidates at all). Pure function, no I/O — the actual decision logic
    behind "ask before recommend", kept separate from run_eligibility_agent
    so it's directly unit-testable without mocking the DB/LLM."""
    if top_count == 0:
        return []
    majority_threshold = max(1, -(-top_count // 2))  # ceil(top_count/2), floor 1
    return [f for f, c in missing_counts.most_common() if c >= majority_threshold]


async def _learn_facts_this_turn(citizen_id: str, message: str, profile: dict) -> tuple[dict, dict]:
    """Extracts facts from THIS message and merges them onto a profile copy
    immediately, instead of only fire-and-forget after the reply (see module
    docstring). Persists to Spring Boot too — cheap (~150ms), well within
    Agent 1's 10s budget — so a later session/turn also remembers it, and
    chat_turn.py skips its own duplicate extraction for this turn (checked
    via agent_outputs["agent1_eligibility"]["profile_learned"])."""
    extracted = await extract_profile_facts(message)
    updates = {k: v for k, v in extracted.items() if (profile or {}).get(k) != v}
    effective_profile = {**profile, **updates}
    if updates and citizen_id:
        await patch_citizen_profile(citizen_id, updates)
    return effective_profile, updates


async def run_eligibility_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    profile = state.get("profile") or {}
    messages = state.get("messages", [])
    last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    effective_profile, learned_this_turn = await _learn_facts_this_turn(
        state.get("citizen_id", ""), last_user_message, profile
    )

    query_text = build_query_string(effective_profile) or last_user_message or "government welfare scheme"

    state_filter = effective_profile.get("state") or None
    candidates = await scheme_vector_search(db, query_text, state_filter=state_filter, limit=15)

    evaluated = []
    for s in candidates:
        result = evaluate_eligibility(effective_profile, s)
        s["_eligibility"] = result
        evaluated.append(s)

    # Eligible first, then insufficient-data (still worth showing — might just
    # need one more field), then not-eligible last. Never invents a ranking
    # signal beyond what evaluate_eligibility actually determined.
    verdict_rank = {"eligible": 0, "insufficient_data": 1, "not_eligible": 2}
    evaluated.sort(key=lambda s: verdict_rank.get(s["_eligibility"]["verdict"], 3))
    top = evaluated[:5]

    missing_counts = Counter(f for s in top for f in s["_eligibility"]["missing_profile_data"])
    systemic_gaps = compute_systemic_gaps(missing_counts, len(top))

    if top and systemic_gaps:
        asks = ", ".join(_FIELD_ASK.get(f, f) for f in systemic_gaps[:4])
        compose_prompt = f"""You are Sathi, a friendly Hinglish-speaking assistant helping an Indian citizen find government welfare schemes.
Citizen's message: "{last_user_message}"

Their profile is too thin to give a real, personalized answer yet — most matching schemes need to know: {asks}.

Write a short, warm reply in Hinglish (2-3 sentences) asking ONLY for these {min(len(systemic_gaps), 4)} things, so you can give a precise answer. Do not list any scheme names yet. Do not ask about anything not in that list. Mention they can also just upload a document via Jan-Sahayak Lens instead of typing answers, or visit a CSC if that's easier."""
        response = await ainvoke_with_fallback(compose_prompt, temperature=0.4)
        reply = response.content.strip()

        state["active_schemes"] = []
        state["reply"] = reply
        state.setdefault("agent_outputs", {})["agent1_eligibility"] = {
            "matched_count": 0,
            "query_text": query_text,
            "asked_for": systemic_gaps[:4],
            "profile_learned": bool(learned_this_turn),
        }
        state.setdefault("reasoning_trace", []).append({
            "agent_name": "agent1_eligibility",
            "tool_called": "clarify_before_recommend",
            "input": query_text,
            "output": f"asked for {systemic_gaps[:4]}",
            "reasoning": f"{len(top)} candidates, systemic gaps: {systemic_gaps}",
        })
        return state

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

    # A one-off gap on a single scheme (not a systemic one, already handled
    # above) still gets a lightweight mention rather than silently dropped.
    one_off_fields = [f for f in missing_counts if f not in systemic_gaps][:2]
    ask_hint = ""
    if one_off_fields:
        asks = ", ".join(_FIELD_ASK.get(f, f) for f in one_off_fields)
        ask_hint = (f"\n\nTo confirm eligibility precisely for the ones marked NEEDS MORE INFO, "
                    f"ask the citizen for: {asks}. They can answer directly, or upload a document via "
                    f"Jan-Sahayak Lens to fill it in automatically. If they can't do either right now, "
                    f"mention they can get help in person at their nearest CSC (Common Service Centre) instead.")

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
        "profile_learned": bool(learned_this_turn),
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent1_eligibility",
        "tool_called": "scheme_vector_search + evaluate_eligibility",
        "input": query_text,
        "output": f"{len(top)} schemes",
        "reasoning": f"state_filter={state_filter}",
    })
    return state
