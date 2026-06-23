"""
run_myscheme_batch.py — standalone one-off runner for a bounded MyScheme
sync, separate from the HTTP endpoint (POST /orchestrator/admin/discovery/run)
because fetch_myscheme_candidates() makes synchronous, rate-limited (2s)
requests.get() calls — running that inline inside a FastAPI request handler
blocks the whole event loop for the batch's duration. This script runs as
its own process instead, so the live server stays responsive.

Usage:
    python -m ai_service.scripts.run_myscheme_batch --limit 350
"""
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from ai_service.db.mongo import get_db  # noqa: E402
from ai_service.discovery.sources.myscheme import fetch_myscheme_candidates  # noqa: E402
from ai_service.discovery.agent2 import _to_scheme_doc  # noqa: E402
from ai_service.discovery.upsert import diff_upsert_schemes  # noqa: E402


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=350)
    parser.add_argument("--offset", type=int, default=0,
                        help="Search-index offset to start from — pass the count of schemes already "
                             "synced, or re-runs just re-fetch (and diff-skip) the same first N schemes.")
    args = parser.parse_args()

    print(f"Fetching up to {args.limit} MyScheme schemes from offset {args.offset} (2s rate limit between requests)...")
    candidates = fetch_myscheme_candidates(limit=args.limit, start_offset=args.offset)
    print(f"Fetched {len(candidates)} candidates. Running diff-upsert (Gemini/Groq extraction + embedding for new/changed only)...")

    docs = [_to_scheme_doc(c) for c in candidates]
    counts = await diff_upsert_schemes(get_db(), docs)
    print(f"Done. {counts}")

    total = await get_db()["schemes"].count_documents({})
    print(f"Total schemes in collection now: {total}")


if __name__ == "__main__":
    asyncio.run(main())
