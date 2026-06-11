"""
upsert.py — content-hash diff + MongoDB upsert, per CLAUDE.md's pipeline/upsert.py spec:

    - scheme_code = unique key
    - Content hash unchanged -> skip (no DB write, no LLM/embedding call)
    - Content changed -> update + flag needs_embedding=true
    - New scheme -> insert + flag needs_embedding=true

This is the piece that makes Agent 2 (and the migration backfill) cheap to
re-run: only schemes whose source text actually changed pay for a Gemini
extraction call + an embedding call. Everything else is a single indexed
lookup.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.db.embeddings import embed_text
from ai_service.discovery.normalizer import extract_eligibility_rules

logger = logging.getLogger(__name__)


def compute_content_hash(scheme: dict) -> str:
    """Hash of the fields that matter for eligibility/benefit meaning — not applyUrl
    formatting or document list ordering, which can change without the scheme itself
    having changed."""
    blob = "|".join([
        scheme.get("name", ""),
        scheme.get("benefitAmount", ""),
        scheme.get("eligibilityText", ""),
    ])
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def diff_upsert_scheme(db: AsyncIOMotorDatabase, scheme: dict) -> str:
    """Upserts one scheme dict (must have schemeCode, name, benefitAmount, eligibilityText).
    Returns one of "skipped" | "updated" | "inserted"."""
    scheme_code = scheme["schemeCode"]
    new_hash = compute_content_hash(scheme)

    existing = await db["schemes"].find_one(
        {"schemeCode": scheme_code}, {"contentHash": 1, "eligibilityRules": 1}
    )

    # Don't skip docs whose rules extraction previously failed (empty rules despite
    # having eligibility text) — extract_eligibility_rules returns {} on LLM quota
    # exhaustion, and a plain hash-skip would freeze that hole in permanently
    # (observed 2026-07-03: 653/984 schemes stuck with empty rules after batches
    # ran during Gemini/Groq quota exhaustion).
    rules_missing = (
        existing is not None
        and not existing.get("eligibilityRules")
        and bool((scheme.get("eligibilityText") or "").strip())
    )
    if existing and existing.get("contentHash") == new_hash and not rules_missing:
        return "skipped"

    rules = await extract_eligibility_rules(
        scheme.get("name", ""), scheme.get("eligibilityText", ""), scheme.get("benefitAmount", "")
    )
    scheme["eligibilityRules"] = rules
    # CLAUDE.md's schemes schema has top-level `category` (used by Agent 1's re-ranking in
    # graph/agents/eligibility.py's _scheme_blob) separate from eligibilityRules — populate it
    # from the structured extraction instead of leaving it always empty.
    scheme["category"] = sorted(set(rules.get("category", []) + rules.get("occupation", [])))
    search_text = f"Scheme: {scheme.get('name','')}\nBenefit: {scheme.get('benefitAmount','')}\nEligibility: {scheme.get('eligibilityText','')}"
    scheme["embedding"] = embed_text(search_text)
    scheme["contentHash"] = new_hash
    scheme["needsEmbedding"] = True  # per CLAUDE.md — signals downstream Atlas re-index; embedding is also set directly above
    scheme["lastUpdated"] = datetime.now(timezone.utc)

    result = await db["schemes"].update_one(
        {"schemeCode": scheme_code}, {"$set": scheme}, upsert=True
    )
    return "inserted" if result.upserted_id else "updated"


async def diff_upsert_schemes(db: AsyncIOMotorDatabase, schemes: list[dict], concurrency: int = 8) -> dict:
    """Runs diff_upsert_scheme over a batch concurrently (bounded by `concurrency`,
    since each changed/new scheme costs a Gemini call), returns counts by outcome.

    Real bug found and fixed here: plain asyncio.gather() propagates the FIRST
    exception any single scheme raises and cancels every other in-flight task —
    one malformed scheme or one transient Mongo hiccup silently killed an entire
    300+ scheme batch with no further progress logged (discovered when a 15-min
    MyScheme sync only landed 5 of an expected ~300 schemes). Each scheme's
    failure is now caught and counted individually, matching the "self-healing
    on source failure" contract agent2.py's docstring already promises."""
    counts = {"skipped": 0, "updated": 0, "inserted": 0, "failed": 0}
    total = len(schemes)
    done = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(scheme: dict) -> None:
        nonlocal done
        try:
            async with semaphore:
                outcome = await diff_upsert_scheme(db, scheme)
            counts[outcome] += 1
        except Exception as e:
            logger.warning("diff_upsert failed for schemeCode=%s (%s: %s) — skipping this scheme",
                            scheme.get("schemeCode"), e.__class__.__name__, e)
            counts["failed"] += 1
        finally:
            done += 1
            if done % 25 == 0 or done == total:
                logger.info("diff_upsert progress: %d/%d %s", done, total, counts)

    await asyncio.gather(*(_one(s) for s in schemes))
    logger.info("diff_upsert_schemes done: %s", counts)
    return counts
