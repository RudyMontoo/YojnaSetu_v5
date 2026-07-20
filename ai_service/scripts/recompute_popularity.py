"""
recompute_popularity.py — writes a `popularityScore` onto every scheme so the
catalogue can surface trending / most-applied / newest schemes FIRST instead of
alphabetically.

Signals, strongest to weakest (a real application counts far more than a search
impression):
    applied  (applications collection)      x5
    saved    (trend_events event_type=save) x3
    viewed   (trend_events event_type=view) x2
    searched (trend_events event_type=search) x1

trend_events has a 30-day TTL, so this is naturally a rolling "recently trending"
window. Schemes with no activity get score 0 and fall back to lastUpdated order
(newest first) in the catalogue sort. Re-run periodically (or wire into the
existing admin trend recompute) as real traffic accrues.

Usage:  python -m ai_service.scripts.recompute_popularity
"""
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from ai_service.db.mongo import get_db  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recompute_popularity")

WEIGHTS = {"applied": 5, "save": 3, "view": 2, "search": 1}


async def recompute() -> dict:
    db = get_db()
    scores: dict[str, int] = {}

    # trend_events (rolling 30d via TTL) grouped by scheme_code + event_type
    async for row in db["trend_events"].aggregate([
        {"$group": {"_id": {"code": "$scheme_code", "type": "$event_type"}, "n": {"$sum": 1}}},
    ]):
        code = row["_id"].get("code")
        etype = row["_id"].get("type")
        if code and etype in WEIGHTS:
            scores[code] = scores.get(code, 0) + WEIGHTS[etype] * row["n"]

    # applications — the strongest signal (someone actually applied)
    async for row in db["applications"].aggregate([
        {"$group": {"_id": "$schemeCode", "n": {"$sum": 1}}},
    ]):
        code = row["_id"]
        if code:
            scores[code] = scores.get(code, 0) + WEIGHTS["applied"] * row["n"]

    # Reset everyone to 0 first (so schemes that fell out of the 30d window drop),
    # then set the active ones. Two bulk writes, no per-doc round-trips.
    await db["schemes"].update_many({"popularityScore": {"$ne": 0}}, {"$set": {"popularityScore": 0}})
    updated = 0
    for code, score in scores.items():
        if score:
            res = await db["schemes"].update_one({"schemeCode": code}, {"$set": {"popularityScore": score}})
            updated += res.modified_count

    # Index so the catalogue's [popularityScore desc, lastUpdated desc] sort is cheap.
    await db["schemes"].create_index([("popularityScore", -1), ("lastUpdated", -1)])

    summary = {"schemes_with_activity": len(scores), "schemes_updated": updated}
    logger.info("popularity recompute done: %s", summary)
    # show the top few for a sanity check
    top = await db["schemes"].find(
        {"popularityScore": {"$gt": 0}}, {"_id": 0, "name": 1, "popularityScore": 1}
    ).sort("popularityScore", -1).limit(5).to_list(length=5)
    for t in top:
        logger.info("  #%s  %s", t["popularityScore"], t["name"][:60])
    return summary


if __name__ == "__main__":
    asyncio.run(recompute())
