"""
run_discovery_job.py — the scheduled entrypoint for Agent 2 Discovery.

This is what the Azure Container Apps cron Job (`discovery-cron`, daily ~02:00
IST) executes. It's deliberately thin: connect to Mongo via the same lazy
get_db() the app uses, run one bounded discovery pass, print the summary, exit.

Why a Job and not an in-process scheduler: the app containers are request-serving
ASGI processes; a 10–40 min rate-limited scrape (2s/request) has no business
running inside them. A separate Job gets its own timeout, its own CPU, and its
own retry policy, and scales to zero when idle.

Freshness-over-completeness by design: diff_upsert is self-healing (per-scheme
try/except; empty-rules holes re-extract on a later run), so even if the LLM
quota is tight, schemes still upsert with current name/benefit/applyUrl and the
eligibility rules fill in on subsequent nights.

Env:
    MONGODB_URI, MONGODB_DB          — required (set by the Job, same secrets as the app)
    DISCOVERY_MYSCHEME_LIMIT         — how many MyScheme listings to sweep this run (default 300)
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Harmless in cloud (no .env file); convenient when run locally.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=False)

from ai_service.db.mongo import get_db  # noqa: E402
from ai_service.discovery.agent2 import run_discovery  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="[DISCOVERY] %(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("discovery_job")


async def main() -> int:
    limit = int(os.getenv("DISCOVERY_MYSCHEME_LIMIT", "300"))
    logger.info("Starting scheduled discovery pass (myscheme_limit=%d)", limit)
    try:
        summary = await run_discovery(get_db(), myscheme_limit=limit)
    except Exception as e:  # a hard failure (e.g. Mongo unreachable) should fail the Job
        logger.exception("Discovery pass failed: %s", e)
        return 1
    logger.info("Discovery pass complete: %s", summary)
    # A run that reached every source but found nothing is already logged to
    # agent_alerts inside run_discovery — surface it here too, but don't fail the
    # Job for it (an empty PIB feed on a quiet news day is not an error).
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
