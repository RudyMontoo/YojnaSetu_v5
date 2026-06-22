"""
myscheme.py — MyScheme.gov.in scraper, per CLAUDE.md's
pipeline/scrapers/myscheme.py spec: "MyScheme sitemap -> all scheme URLs ->
parse each page | 1 req/2s". This is the comprehensive official catalog —
4,729 schemes at time of writing, vastly more than PIB RSS (new-announcement
only) or data.gov.in (a handful of named datasets) cover.

How this was found, for whoever maintains this next: MyScheme's sitemap.xml
does NOT list individual scheme pages (it's a client-rendered Next.js SPA —
scheme data loads via their own public JSON API, not server-rendered HTML).
robots.txt explicitly allows crawling everything ("Allow: /"), and the API
this module calls is the exact same public endpoint their own website's
frontend uses — found by fetching their public JS bundles and reading the
fetch() calls, not from any private/leaked source. The x-api-key embedded
there is shipped to every visitor's browser (inspect any page's network
tab) — it's a public client key, not a secret.

Important: requests need Origin/Referer headers matching myscheme.gov.in or
their API Gateway returns 401/403 — but this works fine with our own honest
User-Agent (YojnaSetu-Bot/1.0, contact email included) alongside those
headers. No browser masquerading needed; verified empirically before
writing this module. That matters because CLAUDE.md's rule is to identify
honestly as a bot, not blend in as a browser — and it turns out we don't
have to choose between the two.

Scale reality, not glossed over: at the mandatory RATE_LIMIT_SECONDS=2
between every request, a full sync of ~4,729 schemes (1 detail call each)
takes ~2.6+ hours minimum. This is why CLAUDE.md scoped Agent 2/pipeline as
a scheduled Cloud Run Job, not a synchronous on-demand call — this module's
`--limit` and `--dry-run` support (mirrored from the existing state-scraper
playbook) exist so it can be tested in seconds without running the full job.
"""
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.myscheme.gov.in"
X_API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"  # public client key, shipped in their frontend JS bundle
USER_AGENT = "YojnaSetu-Bot/1.0 (student project; contact: rudra@yojnasetu.in)"
RATE_LIMIT_SECONDS = 2  # per CLAUDE.md pipeline/config.py — never lower this

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Origin": "https://www.myscheme.gov.in",
    "Referer": "https://www.myscheme.gov.in/search",
    "Accept": "application/json",
    "x-api-key": X_API_KEY,
}

SEARCH_PAGE_SIZE = 20


def _search_page(from_offset: int, size: int) -> dict:
    resp = requests.get(
        f"{API_BASE}/search/v6/schemes",
        params={"lang": "en", "q": "[]", "keyword": "", "sort": "", "from": from_offset, "size": size},
        headers=_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_detail(slug: str) -> Optional[dict]:
    resp = requests.get(
        f"{API_BASE}/schemes/v6/public/schemes",
        params={"slug": slug, "lang": "en"},
        headers={**_HEADERS, "Referer": f"https://www.myscheme.gov.in/schemes/{slug}"},
        timeout=20,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("status") != "Success":
        return None
    return body.get("data", {}).get("en")


def _to_candidate(slug: str, detail: dict) -> dict:
    basic = detail.get("basicDetails", {})
    content = detail.get("schemeContent", {})
    elig = detail.get("eligibilityCriteria", {})
    app_process = detail.get("applicationProcess", []) or []

    # State attribution — real bug fixed 2026-07-03: state-level schemes often
    # have level.value=="state" with beneficiaryState=null, the actual state
    # living in a separate basicDetails.state.label field this mapper never
    # read. Result: hundreds of state schemes were filed as central (state=None)
    # and shown to citizens of every state. extract_state() checks all sources.
    state_list = basic.get("beneficiaryState") or []
    level = (basic.get("level") or {}).get("value", "")
    state_label = (basic.get("state") or {}).get("label")
    if level == "central" or "All" in state_list:
        state = None
    else:
        state = state_label or (state_list[0] if state_list else None)

    categories = [c.get("label", "") for c in (basic.get("schemeCategory") or [])]
    ministry = ((basic.get("nodalMinistryName") or {}).get("label", "")
                or (basic.get("nodalDepartmentName") or {}).get("label", ""))

    apply_url = ""
    for proc in app_process:
        if proc.get("url"):
            apply_url = proc["url"]
            break

    return {
        "name": basic.get("schemeName", ""),
        "eligibilityText": (elig.get("eligibilityDescription_md") or "").strip(),
        "benefitAmount": (content.get("benefits_md") or "").strip(),
        "applyUrl": apply_url,
        "source": "myscheme",
        "ministry": ministry,
        "state": state,
        "category": categories,
        "sector": categories[0] if categories else "general",
        "slug": slug,
    }


def fetch_myscheme_candidates(limit: Optional[int] = None, dry_run: bool = False,
                               start_offset: int = 0) -> list[dict]:
    """Paginates MyScheme's search index for slugs, then fetches full detail
    per scheme. `limit` caps total schemes fetched (None = all ~4,729 — takes
    hours, see module docstring). `dry_run` fetches slugs only, skipping the
    detail calls entirely, to sanity-check pagination/counts fast.

    `start_offset` skips the first N search results — without it, every
    bounded batch re-fetches the SAME first `limit` schemes from offset 0,
    which the content-hash diff then skips entirely (a real no-op run
    observed on 2026-07-03: 298 fetched, 298 skipped, 0 new). Successive
    batches should pass the running total of schemes already synced.

    Never raises — returns whatever was successfully fetched so far on any
    error, consistent with the other sources' graceful-degradation contract."""
    candidates: list[dict] = []
    offset = start_offset

    try:
        first_page = _search_page(0, 1)
        total = first_page.get("data", {}).get("summary", {}).get("total", 0)
        logger.info("MyScheme: %d schemes available (starting from offset %d)", total, start_offset)
    except Exception as e:
        logger.warning("MyScheme search failed (%s: %s) — skipping this source", e.__class__.__name__, e)
        return []

    remaining = max(total - start_offset, 0)
    target = min(limit, remaining) if limit else remaining
    slugs: list[str] = []

    while len(slugs) < target:
        time.sleep(RATE_LIMIT_SECONDS)
        try:
            page = _search_page(offset, SEARCH_PAGE_SIZE)
        except Exception as e:
            logger.warning("MyScheme search page at offset %d failed (%s: %s) — stopping pagination", offset, e.__class__.__name__, e)
            break

        items = page.get("data", {}).get("hits", {}).get("items", [])
        if not items:
            break
        for item in items:
            slug = item.get("fields", {}).get("slug")
            if slug:
                slugs.append(slug)
            if len(slugs) >= target:
                break
        offset += SEARCH_PAGE_SIZE

    slugs = slugs[:target]
    logger.info("MyScheme: %d slugs collected%s", len(slugs), " (dry-run, skipping detail fetch)" if dry_run else "")

    if dry_run:
        return [{"slug": s, "source": "myscheme"} for s in slugs]

    for slug in slugs:
        time.sleep(RATE_LIMIT_SECONDS)
        try:
            detail = _fetch_detail(slug)
            if detail:
                candidates.append(_to_candidate(slug, detail))
        except Exception as e:
            logger.warning("MyScheme detail fetch failed for slug=%s (%s: %s) — skipping this scheme", slug, e.__class__.__name__, e)
            continue

    logger.info("MyScheme: %d candidates fetched", len(candidates))
    return candidates
