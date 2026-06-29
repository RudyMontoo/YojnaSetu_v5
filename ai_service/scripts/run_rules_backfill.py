"""
run_rules_backfill.py — re-extracts structured eligibilityRules for schemes
whose extraction previously failed (empty rules + non-empty eligibilityText).

Why this exists: extract_eligibility_rules() returns {} on LLM quota
exhaustion, and until upsert.py's skip-condition fix (2026-07-03) those
holes were frozen in permanently by the content-hash skip. 653/984 schemes
were stuck that way after batches ran during Gemini/Groq daily-quota
exhaustion. This script heals them WITHOUT refetching anything from
MyScheme — the source text is already in Mongo, only the LLM call is
needed.

Quota-aware by design: sequential (concurrency 1) with a configurable
pause between calls, and it counts consecutive failures — if the LLM is
still quota-dead it stops early instead of burning the rest of the day's
tokens on 653 doomed calls. Safe to re-run any time; already-healed docs
don't match the query.

Usage:
    python -m ai_service.scripts.run_rules_backfill --limit 200 --pause 5
"""
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from ai_service.db.mongo import get_db  # noqa: E402
from ai_service.discovery.normalizer import extract_eligibility_rules  # noqa: E402

MAX_CONSECUTIVE_FAILURES = 8


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200, help="max docs to attempt this run")
    parser.add_argument("--pause", type=float, default=5.0, help="seconds between LLM calls (quota-friendly)")
    args = parser.parse_args()

    db = get_db()
    query = {"eligibilityRules": {}, "eligibilityText": {"$nin": ["", None]}}
    total_broken = await db["schemes"].count_documents(query)
    print(f"{total_broken} schemes have empty rules despite eligibility text; attempting up to {args.limit} this run.")

    cursor = db["schemes"].find(query, {"schemeCode": 1, "name": 1, "eligibilityText": 1, "benefitAmount": 1}).limit(args.limit)
    docs = await cursor.to_list(length=args.limit)

    healed = 0
    still_failing = 0
    consecutive_failures = 0

    for i, doc in enumerate(docs, 1):
        rules = await extract_eligibility_rules(
            doc.get("name", ""), doc.get("eligibilityText", ""), doc.get("benefitAmount", "")
        )
        if rules:
            category = sorted(set(rules.get("category", []) + rules.get("occupation", [])))
            await db["schemes"].update_one(
                {"_id": doc["_id"]},
                {"$set": {"eligibilityRules": rules, "category": category}},
            )
            healed += 1
            consecutive_failures = 0
        else:
            still_failing += 1
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"Stopping early: {consecutive_failures} consecutive extraction failures — "
                      f"LLM quota likely still exhausted. Re-run later; progress is saved per-doc.")
                break

        if i % 20 == 0 or i == len(docs):
            print(f"progress: {i}/{len(docs)} attempted, {healed} healed, {still_failing} still failing")
        await asyncio.sleep(args.pause)

    remaining = await db["schemes"].count_documents(query)
    print(f"Done. healed={healed} still_failing={still_failing} | remaining broken in collection: {remaining}")


if __name__ == "__main__":
    asyncio.run(main())
