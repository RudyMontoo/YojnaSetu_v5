"""
financial_planning.py — Agent 7 (Financial Planning), per CLAUDE.md:
"Total annual benefit calculation across all eligible schemes. Month-by-
month payment calendar. Benefit-to-effort ratio ranking."
Endpoint contract: GET /agents/financial-plan -> {total_annual_benefit,
breakdown, calendar, ranked}.

Three simplifications, stated plainly rather than silently assumed:

1. `total_annual_benefit_inr` only sums `direct_transfer` amounts (see
   utils/benefit_parser.py) — guaranteed recurring cash. `conditional_payout`
   schemes (accident/death compensation etc.) are listed separately in
   `contingent_benefits`, not folded into the routine total — a citizen
   should not be told to expect Rs 5 lakh/year just because one eligible
   scheme pays that IF they suffer a disabling accident.

2. "Month-by-month calendar" — scheme data doesn't carry real disbursal-month
   data (most say "annual" or "monthly", not "paid every March"). Monthly
   benefits are spread evenly across all 12 months; annual/one-time benefits
   go in a single "annual_lump_sum" bucket rather than an invented month.

3. "Effort" has no real data source yet — document count is used as a proxy
   (more required documents generally does mean more citizen effort), an
   honest heuristic, not measured difficulty. Worth replacing once Agent 3
   (Application Guidance) exists and could supply a real effort signal.
"""
import logging

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.agent.yojna_sathi import UserProfile, score_eligibility
from ai_service.db.vector_search import scheme_vector_search
from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.graph.state import GraphState
from ai_service.utils.benefit_parser import extract_benefit_amount

logger = logging.getLogger(__name__)

ELIGIBILITY_SCORE_THRESHOLD = 50
MAX_SCHEMES_TO_PLAN = 10  # bounds LLM calls (one per scheme for benefit parsing) — top-N by eligibility score


def _scheme_blob(scheme: dict) -> str:
    return " ".join([
        scheme.get("name", ""),
        scheme.get("eligibilityText", ""),
        scheme.get("benefitAmount", ""),
        " ".join(scheme.get("category", [])),
        scheme.get("state") or "",
    ])


async def build_financial_plan(profile_dict: dict, db: AsyncIOMotorDatabase) -> dict:
    known_fields = set(UserProfile.__dataclass_fields__.keys())
    profile = UserProfile(**{k: v for k, v in profile_dict.items() if k in known_fields})

    query_text = profile.to_query_string()
    candidates = await scheme_vector_search(db, query_text, state_filter=profile.state, limit=30)

    scored = [(score_eligibility(_scheme_blob(s), profile), s) for s in candidates]
    eligible = [(score, s) for score, s in scored if score >= ELIGIBILITY_SCORE_THRESHOLD]
    eligible.sort(key=lambda t: t[0], reverse=True)
    top_eligible = eligible[:MAX_SCHEMES_TO_PLAN]

    breakdown = []
    total_annual = 0.0
    monthly_calendar = [0.0] * 12
    annual_lump_sum_items = []
    contingent_benefits = []

    for score, scheme in top_eligible:
        benefit = await extract_benefit_amount(scheme.get("benefitAmount", ""))
        effort = max(len(scheme.get("documents", [])), 1)

        item = {
            "schemeCode": scheme.get("schemeCode"),
            "name": scheme.get("name"),
            "eligibilityScore": score,
            "benefitAmount": scheme.get("benefitAmount", ""),
            "benefit_type": benefit["benefit_type"],
            "amount_inr": benefit["amount_inr"],
            "frequency": benefit["frequency"],
            "annualized_inr": benefit["annualized_inr"],
            "effort_documents_required": effort,
            "benefit_effort_ratio": round(benefit["annualized_inr"] / effort, 2) if benefit["annualized_inr"] else None,
        }
        breakdown.append(item)

        if benefit["benefit_type"] == "conditional_payout" and benefit["amount_inr"]:
            contingent_benefits.append({
                "schemeCode": scheme.get("schemeCode"), "name": scheme.get("name"),
                "amount_inr": benefit["amount_inr"], "note": "paid only if the triggering event occurs — not routine income",
            })
        elif benefit["annualized_inr"]:  # direct_transfer only, per extract_benefit_amount's contract
            total_annual += benefit["annualized_inr"]
            if benefit["frequency"] == "monthly":
                for m in range(12):
                    monthly_calendar[m] += benefit["amount_inr"]
            else:
                annual_lump_sum_items.append({"schemeCode": scheme.get("schemeCode"), "name": scheme.get("name"), "amount_inr": benefit["amount_inr"]})

    ranked = sorted(
        [b for b in breakdown if b["benefit_effort_ratio"] is not None],
        key=lambda b: b["benefit_effort_ratio"],
        reverse=True,
    )

    reply = await _compose_summary(profile, total_annual, len(breakdown), ranked[:3], contingent_benefits)

    return {
        "total_annual_benefit_inr": round(total_annual, 2),
        "schemes_considered": len(breakdown),
        "breakdown": breakdown,
        "calendar": {
            "monthly_recurring_inr": [round(m, 2) for m in monthly_calendar],
            "annual_lump_sum": annual_lump_sum_items,
        },
        "contingent_benefits": contingent_benefits,
        "ranked_by_benefit_effort_ratio": ranked,
        "reply": reply,
    }


async def _compose_summary(profile: UserProfile, total_annual: float, count: int, top_3: list[dict], contingent: list[dict]) -> str:
    if count == 0:
        return "Abhi tak koi eligible scheme nahi mili jiska clear benefit amount ho. Apna profile aur complete karein — state, income, occupation batayein."

    top_names = ", ".join(f"{s['name']} (₹{s['amount_inr']:,.0f})" for s in top_3 if s.get("amount_inr")) or "koi nahi"
    contingent_note = f" Iske alawa {len(contingent)} schemes hain jo sirf kisi durghatna ya vishesh sthiti mein milengi." if contingent else ""

    prompt = f"""Citizen's profile: {profile.to_query_string()}
Total guaranteed annual benefit across {count} eligible schemes: Rs {total_annual:,.0f}
Best value-for-effort schemes: {top_names}
{f"Also has {len(contingent)} conditional/contingency schemes (compensation paid only if a specific event occurs) — do not include these in the routine annual figure." if contingent else ""}

Write a short, encouraging summary in Hinglish (2-3 sentences) telling the citizen their guaranteed annual benefit and which 1-2 schemes give the best return for the least paperwork effort. Do not conflate the guaranteed total with any contingent/compensation amounts."""

    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.4)
        return response.content.strip()
    except Exception as e:
        logger.warning("Failed to compose financial plan summary: %s", e)
        return f"Aapke liye guaranteed annual benefit ₹{total_annual:,.0f} hai, {count} schemes se.{contingent_note}"


async def run_financial_plan_agent(state: GraphState, db: AsyncIOMotorDatabase) -> GraphState:
    """LangGraph node wrapper for the `financial_plan` intent — same
    build_financial_plan() the standalone GET /agents/financial-plan
    endpoint uses, just fed from GraphState's profile instead of a fetched
    Spring Boot profile. Was previously wired to the placeholder node
    despite this agent being fully built (see docs/status/AGENTS.md)."""
    profile_dict = state.get("profile") or {}
    result = await build_financial_plan(profile_dict, db)

    state["reply"] = result["reply"]
    state.setdefault("agent_outputs", {})["agent7_financial"] = {
        "total_annual_benefit_inr": result["total_annual_benefit_inr"],
        "schemes_considered": result["schemes_considered"],
    }
    state.setdefault("reasoning_trace", []).append({
        "agent_name": "agent7_financial",
        "tool_called": "build_financial_plan",
        "input": profile_dict.get("state", "unknown_state"),
        "output": f"{result['schemes_considered']} schemes, ₹{result['total_annual_benefit_inr']:,.0f}/yr",
        "reasoning": "eligibility_score_threshold=50, top 10 by score",
    })
    return state
