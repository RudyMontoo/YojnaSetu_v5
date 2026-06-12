"""
pib_rss.py — PIB RSS watcher, per CLAUDE.md's pipeline/scrapers/pib_rss.py spec:
"PIB RSS feed -> detect keyword matches -> Gemini extracts eligibility, polls
every 30min". Detection keywords are CLAUDE.md's literal list.

Known limitation, stated plainly rather than silently assumed away: PIB's
site was redesigned and its old static RSS paths (rss/lreleng.xml,
rss/allrel.xml, etc.) now return HTTP 200 with a custom "page not available"
HTML body instead of a real 404 or the feed — so probing for the current
feed URL isn't reliable from here. PIB_RSS_URL is therefore read from an env
var with no working default; if unset or unreachable, this source degrades
to returning an empty list (logged, not silently swallowed) rather than
crashing Agent 2's run. Whoever finds the current feed URL (check PIB's site
directly, or their published API docs) should set PIB_RSS_URL in .env.
"""
import logging
import os
import time
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

# Per CLAUDE.md's PIB RSS detection keywords
DETECTION_KEYWORDS = ["scheme", "yojana", "launch", "welfare", "benefit", "beneficiary", "crore", "lakh", "subsidy"]

USER_AGENT = "YojnaSetu-Bot/1.0 (student project; contact: rudra@yojnasetu.in)"
RATE_LIMIT_SECONDS = 2  # per CLAUDE.md pipeline/config.py — sleep between every HTTP request, never lower this


def _keyword_match(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in DETECTION_KEYWORDS)


def fetch_pib_candidates() -> list[dict]:
    """Returns raw scheme candidates from the PIB RSS feed, or [] if the feed
    isn't configured/reachable. Never raises — Agent 2 must keep running even
    if one source is down."""
    feed_url = os.getenv("PIB_RSS_URL", "").strip()
    if not feed_url:
        logger.info("PIB_RSS_URL not set — skipping PIB RSS source (see module docstring)")
        return []

    try:
        time.sleep(RATE_LIMIT_SECONDS)  # sleep before every outbound request — never lower this, per CLAUDE.md
        resp = requests.get(feed_url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        logger.warning("PIB RSS fetch/parse failed (%s: %s) — skipping this run", e.__class__.__name__, e)
        return []

    candidates = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not _keyword_match(f"{title} {description}"):
            continue
        candidates.append({
            "name": title,
            "eligibilityText": description,
            "benefitAmount": "",
            "applyUrl": link,
            "source": "pib_rss",
        })

    logger.info("PIB RSS: %d keyword-matched candidates", len(candidates))
    return candidates
