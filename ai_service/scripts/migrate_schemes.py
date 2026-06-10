"""
migrate_schemes.py — migration of ai_service/data/schemes/*.json into the
MongoDB `schemes` collection, per CLAUDE.md's schema and Phase 3 of the
v5.0 rebuild plan.

Shares the exact same content-hash diff + upsert path as Agent 2 Discovery
(ai_service/discovery/upsert.py) rather than its own bulk-write logic, so a
scheme discovered by Agent 2 and one migrated by this script land in the
collection the same shape, and re-running this script is cheap: unchanged
schemes are skipped (no Gemini call, no re-embedding), only new/changed ones
pay for extraction + embedding.

Default scope is all central-sector schemes + one pilot state (Uttar
Pradesh, matching the doc's UP/Odisha/Jharkhand pilot). Pass --state for a
different single state, or --all-states for every state file.

Usage:
    python -m ai_service.scripts.migrate_schemes
    python -m ai_service.scripts.migrate_schemes --state maharashtra
    python -m ai_service.scripts.migrate_schemes --all-states
"""
import argparse
import asyncio
import json
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

from ai_service.db.mongo import get_db  # noqa: E402
from ai_service.discovery.upsert import diff_upsert_schemes  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "schemes"


def slugify(*parts: str) -> str:
    joined = "-".join(p for p in parts if p)
    slug = re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")
    return slug[:180]


def load_central_schemes() -> list[dict]:
    docs = []
    for f in sorted(DATA_DIR.glob("*.json")):
        if f.name == "all_schemes.json":
            continue  # redundant aggregate of the same sector files, skip to avoid duplicates
        data = json.loads(f.read_text(encoding="utf-8"))
        sector = data.get("sector", f.stem)
        for s in data.get("schemes", []):
            if s.get("status") not in (None, "active"):
                continue
            name = s.get("name") or s.get("name_en", "")
            docs.append({
                "schemeCode": slugify("central", sector, name),
                "name": name,
                "ministry": s.get("ministry", ""),
                "state": None,
                "category": [],
                "sector": sector,
                "eligibilityText": s.get("eligibility", ""),
                "benefitAmount": s.get("benefit") or s.get("benefit_en", ""),
                "documents": s.get("documents", []),
                "applyUrl": s.get("apply_url", ""),
            })
    return docs


def load_state_schemes(state_file_stem: str) -> list[dict]:
    f = DATA_DIR / "states" / f"{state_file_stem}.json"
    if not f.exists():
        raise FileNotFoundError(f"No state file at {f}")
    data = json.loads(f.read_text(encoding="utf-8"))
    state_en = data.get("state_en", state_file_stem)
    docs = []
    for s in data.get("schemes", []):
        if s.get("status") not in (None, "active"):
            continue
        name = s.get("name") or s.get("name_en", "")
        docs.append({
            "schemeCode": slugify("state", state_file_stem, name),
            "name": name,
            "ministry": "",
            "state": state_en,
            "category": [],
            "sector": s.get("sector", "general"),
            "eligibilityText": s.get("eligibility", ""),
            "benefitAmount": s.get("benefit") or s.get("benefit_en", ""),
            "documents": s.get("documents", []),
            "applyUrl": s.get("apply_url", ""),
        })
    return docs


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="uttar_pradesh", help="state file stem under data/schemes/states/")
    parser.add_argument("--all-states", action="store_true", help="migrate every state file, not just --state")
    args = parser.parse_args()

    print("Loading central-sector schemes...")
    docs = load_central_schemes()
    print(f"  {len(docs)} central schemes loaded")

    if args.all_states:
        state_dir = DATA_DIR / "states"
        for f in sorted(state_dir.glob("*.json")):
            docs.extend(load_state_schemes(f.stem))
    else:
        state_docs = load_state_schemes(args.state)
        docs.extend(state_docs)
        print(f"  {len(state_docs)} {args.state} schemes loaded")

    print(f"\nDiff-upserting {len(docs)} schemes (unchanged ones are skipped — no Gemini/embedding call)...")
    counts = await diff_upsert_schemes(get_db(), docs)
    print(f"\nDone. {counts}")

    total = await get_db()["schemes"].count_documents({})
    print(f"Total schemes now in collection: {total}")


if __name__ == "__main__":
    asyncio.run(main())
