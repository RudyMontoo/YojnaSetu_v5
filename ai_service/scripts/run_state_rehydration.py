"""
run_state_rehydration.py — one-off repair for MyScheme docs ingested before
the state-attribution fix (2026-07-03, see sources/myscheme.py's
_to_candidate): state-level schemes with beneficiaryState=null were filed
as central (state=None) and shown to citizens of every state.

Re-fetches ONLY the detail metadata per already-synced myscheme doc and
updates `state` (and `ministry` if it was empty). Deliberately does NOT
touch eligibilityText/benefitAmount/contentHash — no LLM calls, no
embedding recompute, quota-irrelevant; just the 2s-rate-limited HTTP
fetches (~565 docs ≈ 19 min).

Safe to re-run: docs already carrying a state are skipped by default
(--all to force).

Usage:
    python -m ai_service.scripts.run_state_rehydration [--all] [--limit N]
"""
import argparse
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from ai_service.db.mongo import get_db  # noqa: E402
from ai_service.discovery.sources.myscheme import RATE_LIMIT_SECONDS, _fetch_detail  # noqa: E402


def _extract_state_ministry(detail: dict) -> tuple[str | None, str]:
    basic = detail.get("basicDetails", {})
    state_list = basic.get("beneficiaryState") or []
    level = (basic.get("level") or {}).get("value", "")
    state_label = (basic.get("state") or {}).get("label")
    if level == "central" or "All" in state_list:
        state = None
    else:
        state = state_label or (state_list[0] if state_list else None)
    ministry = ((basic.get("nodalMinistryName") or {}).get("label", "")
                or (basic.get("nodalDepartmentName") or {}).get("label", ""))
    return state, ministry


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="also re-check docs that already have a state")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    db = get_db()
    query = {"discoverySource": "myscheme"}
    if not args.all:
        query["state"] = None
    docs = await db["schemes"].find(query, {"schemeCode": 1, "slug": 1, "name": 1}).to_list(length=args.limit or 10_000)
    # slug isn't stored top-level on scheme docs — recover it from schemeCode
    # ("discovered-myscheme-<slug>").
    print(f"{len(docs)} myscheme docs to re-check (state currently {'any' if args.all else 'None'}).")

    updated = 0
    failed = 0
    unchanged = 0
    for i, doc in enumerate(docs, 1):
        slug = doc.get("slug") or doc["schemeCode"].removeprefix("discovered-myscheme-")
        time.sleep(RATE_LIMIT_SECONDS)
        try:
            detail = _fetch_detail(slug)
        except Exception as e:
            failed += 1
            print(f"  fetch failed for {slug}: {e.__class__.__name__}")
            continue
        if not detail:
            failed += 1
            continue

        state, ministry = _extract_state_ministry(detail)
        updates = {}
        if state:
            updates["state"] = state
        if ministry:
            updates["ministry"] = ministry
        if updates:
            await db["schemes"].update_one({"_id": doc["_id"]}, {"$set": updates})
            updated += 1
        else:
            unchanged += 1

        if i % 25 == 0 or i == len(docs):
            print(f"progress: {i}/{len(docs)} — updated={updated} unchanged={unchanged} failed={failed}")

    total_with_state = await db["schemes"].count_documents({"discoverySource": "myscheme", "state": {"$ne": None}})
    print(f"Done. updated={updated} unchanged={unchanged} failed={failed} | myscheme docs now carrying a state: {total_with_state}")


if __name__ == "__main__":
    asyncio.run(main())
