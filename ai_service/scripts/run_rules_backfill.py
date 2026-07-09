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
pause between calls, and it counts consecutive API FAILURES (not
consecutive empty results — see below) — if the LLM is still quota-dead it
stops early instead of burning the rest of the day's tokens on hundreds of
doomed calls. Safe to re-run any time; already-healed docs don't match the
query.

2026-07-05 fix: originally this script couldn't tell "LLM call failed"
apart from "LLM call succeeded but the scheme's text genuinely has no
extractable eligibility facts" — both looked like an empty {} return, so a
short run of ordinary narrow-eligibility schemes ("Ex-servicemen and war
widows in financial distress" — no income/age/category to extract) would
trip the same "stopping early: quota exhausted" message as a real outage,
which is misleading and stops the run prematurely for no real reason. Now
uses extract_eligibility_rules(raise_on_error=True) so a real API
exception is distinguishable from a clean-but-empty extraction: only real
exceptions count toward the consecutive-failure early-stop; genuinely
unextractable schemes are tracked separately (`no_rules_found`) and don't
block progress on the rest of the batch.

2026-07-09: default provider switched to LOCAL OLLAMA (--provider ollama). The
free cloud tiers (Gemini 20 req/day, Groq's daily token cap) made this backfill
a multi-week drip — a local model has no daily limit and no per-call cost, so
the full ~1,300-scheme backlog can heal in one run. Pass --provider groq/gemini
to use the cloud paths instead. With Ollama the quota-based early-stop and
inter-call pause aren't needed (default pause 0), but the consecutive-failure
guard still catches a dead daemon.

Usage:
    python -m ai_service.scripts.run_rules_backfill --limit 2000        # local Ollama, whole backlog
    python -m ai_service.scripts.run_rules_backfill --provider groq --limit 200 --pause 5
"""
import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from ai_service.db.mongo import get_db  # noqa: E402
from ai_service.discovery.normalizer import extract_eligibility_rules  # noqa: E402

MAX_CONSECUTIVE_FAILURES = 8


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200, help="max docs to attempt this run")
    parser.add_argument("--pause", type=float, default=None,
                        help="seconds between LLM calls (default 0 for ollama, 5 for cloud providers)")
    parser.add_argument("--provider", choices=["ollama", "groq", "gemini"], default="ollama",
                        help="LLM backend: local ollama (no quota, default) or a cloud provider")
    args = parser.parse_args()

    if args.provider == "ollama":
        os.environ["OLLAMA_ENABLED"] = "1"  # llm.py's _ollama_llm is off unless this is set
    pause = args.pause if args.pause is not None else (0.0 if args.provider == "ollama" else 5.0)
    print(f"Using provider={args.provider}, pause={pause}s")

    db = get_db()
    query = {"eligibilityRules": {}, "eligibilityText": {"$nin": ["", None]}}
    total_broken = await db["schemes"].count_documents(query)
    print(f"{total_broken} schemes have empty rules despite eligibility text; attempting up to {args.limit} this run.")

    cursor = db["schemes"].find(query, {"schemeCode": 1, "name": 1, "eligibilityText": 1, "benefitAmount": 1}).limit(args.limit)
    docs = await cursor.to_list(length=args.limit)

    healed = 0
    no_rules_found = 0  # LLM call succeeded, text genuinely has nothing to extract — not a failure
    api_failed = 0      # real exception (quota/network/parse) — this is what should stop the run
    consecutive_failures = 0

    for i, doc in enumerate(docs, 1):
        try:
            rules = await extract_eligibility_rules(
                doc.get("name", ""), doc.get("eligibilityText", ""), doc.get("benefitAmount", ""),
                raise_on_error=True, prefer=args.provider,
            )
        except Exception:
            api_failed += 1
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"Stopping early: {consecutive_failures} consecutive API failures — "
                      f"LLM quota likely exhausted. Re-run later; progress is saved per-doc.")
                break
            if i % 20 == 0 or i == len(docs):
                print(f"progress: {i}/{len(docs)} attempted, {healed} healed, "
                      f"{no_rules_found} genuinely empty, {api_failed} api failures")
            await asyncio.sleep(pause)
            continue

        consecutive_failures = 0  # a clean call (empty or not) means the LLM path is alive
        if rules:
            category = sorted(set(rules.get("category", []) + rules.get("occupation", [])))
            await db["schemes"].update_one(
                {"_id": doc["_id"]},
                {"$set": {"eligibilityRules": rules, "category": category}},
            )
            healed += 1
        else:
            no_rules_found += 1

        if i % 20 == 0 or i == len(docs):
            print(f"progress: {i}/{len(docs)} attempted, {healed} healed, "
                  f"{no_rules_found} genuinely empty, {api_failed} api failures")
        await asyncio.sleep(pause)

    remaining = await db["schemes"].count_documents(query)
    print(f"Done. healed={healed} no_rules_found={no_rules_found} api_failed={api_failed} "
          f"| remaining broken in collection: {remaining}")
    print("Note: 'no_rules_found' schemes have genuinely no income/age/category/occupation facts "
          "in their eligibility text (e.g. narrow criteria like 'ex-servicemen' or 'existing "
          "beneficiaries') — re-running will not change them; they are not stuck on quota.")


if __name__ == "__main__":
    asyncio.run(main())
