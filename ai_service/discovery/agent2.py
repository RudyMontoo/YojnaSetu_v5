"""
agent2.py — Agent 2 (Discovery), orchestrating the source fetchers +
normalizer + diff-upsert pipeline. Per CLAUDE.md: "LangGraph event loop +
httpx + Gemini Flash — persistent scheme ingestion... new Central schemes
live within 60 min of PIB announcement. Self-healing on source failure."

"Self-healing on source failure" here means: one source failing (missing
key, dead URL, network error) never stops the run or crashes the caller —
each source function already returns [] on failure rather than raising, and
this module logs a `agent_alerts` entry when a source produced nothing so
it's visible on /agents/health-style monitoring, without treating it as
fatal.

This module intentionally does NOT include a "poll every 30 minutes"
scheduler loop — that's a deployment concern (Cloud Run Job cron / APScheduler
in-process), not something to bake into the pipeline logic itself. Trigger
this via the manual endpoint (routers/orchestrator_router.py) or a cron job
once one exists.

MyScheme is NOT included by default: unlike PIB RSS / data.gov.in (fast,
bounded calls), a MyScheme sync is 1 request per scheme at a mandatory 2s
rate limit — the full ~4,729-scheme catalog takes hours. Pass
`myscheme_limit` explicitly to include a bounded batch in a given run; the
default on-demand discovery endpoint stays fast without it.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.discovery.sources.datagov import fetch_datagov_candidates
from ai_service.discovery.sources.myscheme import fetch_myscheme_candidates
from ai_service.discovery.sources.pib_rss import fetch_pib_candidates
from ai_service.discovery.upsert import diff_upsert_schemes

logger = logging.getLogger(__name__)


def _slugify(*parts: str) -> str:
    joined = "-".join(p for p in parts if p)
    slug = re.sub(r"[^a-z0-9]+", "-", joined.lower()).strip("-")
    return slug[:180]


def _to_scheme_doc(candidate: dict) -> dict:
    """Normalizes a raw source candidate into the shape diff_upsert_scheme expects
    (same shape scripts/migrate_schemes.py produces, so both paths write compatible
    documents to the same `schemes` collection). MyScheme candidates carry their own
    ministry/state/category — PIB/data.gov.in don't, so those default to Central/generic."""
    return {
        "schemeCode": _slugify("discovered", candidate["source"], candidate.get("slug") or candidate["name"]),
        "name": candidate["name"],
        "ministry": candidate.get("ministry", ""),
        "state": candidate.get("state"),
        "category": candidate.get("category", []),
        "sector": candidate.get("sector", "general"),
        "eligibilityText": candidate.get("eligibilityText", ""),
        "benefitAmount": candidate.get("benefitAmount", ""),
        "documents": [],
        "applyUrl": candidate.get("applyUrl", ""),
        "discoverySource": candidate["source"],
    }


async def run_discovery(db: AsyncIOMotorDatabase, myscheme_limit: Optional[int] = None) -> dict:
    """One discovery pass across all configured sources. Returns a summary dict.
    myscheme_limit=None skips MyScheme entirely (keeps this fast/on-demand-safe);
    pass a number to include a bounded MyScheme batch in this run."""
    pib_candidates = fetch_pib_candidates()
    datagov_candidates = fetch_datagov_candidates()
    myscheme_candidates = fetch_myscheme_candidates(limit=myscheme_limit) if myscheme_limit else []

    all_candidates = pib_candidates + datagov_candidates + myscheme_candidates
    scheme_docs = [_to_scheme_doc(c) for c in all_candidates]

    counts = await diff_upsert_schemes(db, scheme_docs) if scheme_docs else {"skipped": 0, "updated": 0, "inserted": 0}

    summary = {
        "pib_candidates": len(pib_candidates),
        "datagov_candidates": len(datagov_candidates),
        "myscheme_candidates": len(myscheme_candidates),
        **counts,
        "at": datetime.now(timezone.utc),
    }

    if not pib_candidates and not datagov_candidates and not myscheme_candidates:
        await db["agent_alerts"].insert_one({
            "agent_name": "agent2_discovery",
            "alert_type": "no_sources_configured",
            "message": "Discovery run found 0 candidates from all sources — check PIB_RSS_URL / DATAGOVIN_API_KEY / DATAGOVIN_RESOURCE_IDS env vars, or pass myscheme_limit.",
            "at": datetime.now(timezone.utc),
            "resolved": False,
        })
        logger.warning("Agent 2 discovery run found zero candidates from all sources — logged to agent_alerts")

    logger.info("Agent 2 discovery run complete: %s", summary)
    return summary
