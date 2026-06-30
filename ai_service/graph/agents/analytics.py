"""
analytics.py — Agent 10 (Analytics), per CLAUDE.md: weekly admin report
written to the permanent `admin_reports` collection with
{report_date, top_dropoff_schemes, confusing_criteria, state_gaps,
 new_citizens, benefits_unlocked_estimate, narrative}.

Every metric is a plain Mongo aggregation over REAL collections — no LLM
needed for the numbers, so the report generates correctly even during
quota exhaustion. Only the human-readable `narrative` uses one LLM call,
and it falls back to a plain template when that fails.

Honest-metric notes (what each number actually means, not what it sounds
like it means):
- top_dropoff_schemes: schemes with applications stuck in "saved" that
  never progressed — the citizen showed intent then stalled.
- confusing_criteria: schemes frequently shown to citizens (trend_events
  "search") but never saved by anyone — a proxy for "looked at, walked
  away", which may mean confusing eligibility, poor benefit clarity, or
  simply irrelevance. It's a lead for a human to investigate, not a verdict.
- state_gaps: states citizens are actually searching from vs. how many
  state-specific schemes the catalog has for them — low coverage where
  demand exists.
- benefits_unlocked_estimate: null for now, stated plainly — applications
  don't carry a parsed benefit amount, and inventing a number from LLM
  re-parsing would be exactly the kind of fake precision the benefit_parser
  bug taught us to avoid (see memory 2026-07-03). Wire this to real
  disbursal statuses when Agent 3/5 land.

The weekly Sunday-11PM-IST schedule is a deployment concern (Cloud Run Job
cron) — this module only knows how to generate one report on demand.
"""
import logging
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.utils.states import state_match_variants

logger = logging.getLogger(__name__)

WINDOW_DAYS = 7
TOP_N = 5


async def generate_weekly_report(db: AsyncIOMotorDatabase) -> dict:
    """Computes the report over the trailing 7 days, inserts it into
    admin_reports (permanent, per CLAUDE.md), and returns it."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)

    # -- dropoff: applications created in-window still sitting at "saved" --
    dropoff = await db["applications"].aggregate([
        {"$match": {"status": "saved", "appliedAt": {"$gte": since}}},
        {"$group": {"_id": "$schemeCode", "name": {"$first": "$schemeName"}, "stuck": {"$sum": 1}}},
        {"$sort": {"stuck": -1}},
        {"$limit": TOP_N},
    ]).to_list(length=TOP_N)
    top_dropoff_schemes = [f"{d['name'] or d['_id']} ({d['stuck']} stuck at saved)" for d in dropoff]

    # -- confusing criteria: searched often, saved by no one --
    searched = await db["trend_events"].aggregate([
        {"$match": {"at": {"$gte": since}, "event_type": "search"}},
        {"$group": {"_id": "$scheme_code", "name": {"$first": "$scheme_name"}, "searches": {"$sum": 1}}},
        {"$sort": {"searches": -1}},
        {"$limit": 50},
    ]).to_list(length=50)
    saved_codes = set(await db["trend_events"].distinct(
        "scheme_code", {"at": {"$gte": since}, "event_type": "save"}))
    confusing_criteria = [
        f"{s['name'] or s['_id']} (shown {s['searches']}x, saved 0x)"
        for s in searched if s["_id"] not in saved_codes
    ][:TOP_N]

    # -- state gaps: search demand per state vs. state-scheme coverage --
    demand_by_state = await db["trend_events"].aggregate([
        {"$match": {"at": {"$gte": since}, "user_state": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$user_state", "events": {"$sum": 1}}},
        {"$sort": {"events": -1}},
    ]).to_list(length=50)
    state_gaps = []
    for entry in demand_by_state:
        state = entry["_id"]
        # Match both representations ("UP" and "Uttar Pradesh") — profiles carry
        # codes, scheme docs carry full names. See utils/states.py for the bug story.
        coverage = await db["schemes"].count_documents({"state": {"$in": state_match_variants(state)}})
        if coverage < 10:  # demand exists, catalog is thin
            state_gaps.append(f"{state}: {entry['events']} events this week but only {coverage} state-specific schemes in catalog")

    # -- new citizens: users created in-window (Spring Boot writes createdAt) --
    new_citizens = await db["users"].count_documents({"createdAt": {"$gte": since.replace(tzinfo=None)}})

    report = {
        "report_date": now,
        "window_days": WINDOW_DAYS,
        "top_dropoff_schemes": top_dropoff_schemes,
        "confusing_criteria": confusing_criteria,
        "state_gaps": state_gaps,
        "new_citizens": new_citizens,
        # Honest null — see module docstring. Never invent a rupee figure.
        "benefits_unlocked_estimate": None,
        "narrative": "",
    }

    report["narrative"] = await _compose_narrative(report)

    await db["admin_reports"].insert_one(dict(report))
    report.pop("_id", None)  # insert_one mutates the dict with the ObjectId
    logger.info("Agent 10: weekly report generated (new_citizens=%d, dropoffs=%d, confusing=%d, gaps=%d)",
                new_citizens, len(top_dropoff_schemes), len(confusing_criteria), len(state_gaps))
    return report


def _template_narrative(r: dict) -> str:
    return (
        f"Weekly report ({r['window_days']} days): {r['new_citizens']} new citizens joined. "
        f"{len(r['top_dropoff_schemes'])} schemes have citizens stuck at 'saved'. "
        f"{len(r['confusing_criteria'])} schemes were shown often but never saved (possible confusing criteria). "
        f"{len(r['state_gaps'])} states show search demand with thin catalog coverage. "
        f"Benefits-unlocked estimate is not yet computable (no disbursal tracking wired)."
    )


async def _compose_narrative(report: dict) -> str:
    prompt = f"""You are writing the narrative section of a weekly analytics report for the admins of Yojna Setu, an Indian welfare-scheme assistant. Be factual and concise (4-6 sentences), flag what needs human attention, do not invent numbers not present below.

New citizens this week: {report['new_citizens']}
Schemes with citizens stuck at 'saved' (dropoff): {report['top_dropoff_schemes'] or 'none'}
Schemes shown often but never saved (possible confusing criteria): {report['confusing_criteria'] or 'none'}
State coverage gaps (demand vs catalog): {report['state_gaps'] or 'none'}
Benefits unlocked estimate: not computable yet (no disbursal tracking)."""
    try:
        response = await ainvoke_with_fallback(prompt, temperature=0.3)
        return response.content.strip()
    except Exception as e:
        logger.warning("Agent 10 narrative LLM call failed (%s) — using template narrative", e.__class__.__name__)
        return _template_narrative(report)
