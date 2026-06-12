"""
datagov.py — data.gov.in REST API puller, per CLAUDE.md's
pipeline/scrapers/datagov.py spec: "data.gov.in API -> PM-KISAN, PMAY, NSP,
Ayushman datasets, API key, no rate limit".

Known limitation, stated plainly: this needs both DATAGOVIN_API_KEY (a free
key from a data.gov.in account) and specific dataset resource IDs, which can
only be found by browsing https://data.gov.in's catalog UI with that key —
they aren't guessable. DATAGOVIN_RESOURCE_IDS is a comma-separated env var
left empty by default; whoever sets up the account should populate it after
finding the relevant PM-KISAN/PMAY/NSP/Ayushman dataset IDs. Until both are
set, this source degrades to an empty list (logged), same as pib_rss.py —
Agent 2 must keep running even with zero configured sources.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.data.gov.in/resource"


def _fetch_resource(resource_id: str, api_key: str, limit: int = 50) -> list[dict]:
    url = f"{API_BASE}/{resource_id}"
    resp = requests.get(url, params={"api-key": api_key, "format": "json", "limit": limit}, timeout=20)
    resp.raise_for_status()
    return resp.json().get("records", [])


def fetch_datagov_candidates() -> list[dict]:
    """Returns raw scheme candidates from configured data.gov.in resources, or []
    if no API key / resource IDs are configured. Never raises."""
    api_key = os.getenv("DATAGOVIN_API_KEY", "").strip()
    resource_ids = [r.strip() for r in os.getenv("DATAGOVIN_RESOURCE_IDS", "").split(",") if r.strip()]

    if not api_key or not resource_ids:
        logger.info("DATAGOVIN_API_KEY or DATAGOVIN_RESOURCE_IDS not set — skipping data.gov.in source (see module docstring)")
        return []

    candidates = []
    for resource_id in resource_ids:
        try:
            records = _fetch_resource(resource_id, api_key)
        except Exception as e:
            logger.warning("data.gov.in fetch failed for resource %s (%s: %s) — skipping this resource", resource_id, e.__class__.__name__, e)
            continue

        for rec in records:
            name = rec.get("scheme_name") or rec.get("name") or rec.get("title")
            if not name:
                continue
            candidates.append({
                "name": name,
                "eligibilityText": rec.get("eligibility", "") or rec.get("description", ""),
                "benefitAmount": rec.get("benefit", "") or rec.get("amount", ""),
                "applyUrl": rec.get("url", ""),
                "source": f"datagov:{resource_id}",
            })

    logger.info("data.gov.in: %d candidates across %d resources", len(candidates), len(resource_ids))
    return candidates
