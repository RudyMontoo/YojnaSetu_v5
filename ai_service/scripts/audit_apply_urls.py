"""
audit_apply_urls.py — Problem 5 (link audit): checks every scheme's
`applyUrl` for a genuine dead link (DNS failure, connection refused,
timeout, or a 4xx/5xx from the server) and reports them, rather than
silently leaving broken government links in the catalogue.

Deliberately does NOT auto-fix or guess a replacement URL — a scheme code
whose applyUrl looks wrong or resolves to the wrong ministry is a job for a
human to verify, not for this script to silently "correct". It only
classifies and reports.

Rate-limited like the rest of the discovery pipeline (RATE_LIMIT_SECONDS,
same convention as pipeline/config.py) — this hits real government servers,
so it must not hammer them just because it's convenient to run fast.

Usage:  python -m ai_service.scripts.audit_apply_urls [--limit N] [--out FILE]
Writes a JSON report to ai_service/scripts/apply_url_audit_report.json by
default (gitignored — this is a data artifact, not code).
"""
import argparse
import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)

import httpx  # noqa: E402

from ai_service.db.mongo import get_db  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit_apply_urls")

RATE_LIMIT_SECONDS = 2  # same politeness convention as pipeline/config.py — never lower this
REQUEST_TIMEOUT_SECONDS = 15
# A real browser UA — several .gov.in/.nic.in sites 403/timeout on bare httpx/curl
# UAs (confirmed during this audit: pmayg.gov.in behaved this way), which would
# otherwise be misreported as "dead" when the domain and page are actually fine.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


async def _check_url(client: httpx.AsyncClient, url: str) -> dict:
    if not url or not url.strip():
        return {"status": "missing", "detail": "no applyUrl set"}
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT_SECONDS,
                                 headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        if resp.status_code >= 400:
            return {"status": "http_error", "detail": f"HTTP {resp.status_code}", "final_url": str(resp.url)}
        return {"status": "ok", "detail": f"HTTP {resp.status_code}", "final_url": str(resp.url)}
    except httpx.ConnectTimeout:
        return {"status": "timeout", "detail": "connection timed out"}
    except httpx.ConnectError as e:
        # httpx wraps DNS failures (socket.gaierror) in ConnectError — distinguish
        # "domain doesn't exist" from "server refused" for a clearer report.
        msg = str(e)
        detail = "DNS resolution failed (domain likely doesn't exist)" if "gaierror" in msg or "Name or service not known" in msg else msg
        return {"status": "connect_failed", "detail": detail}
    except httpx.HTTPError as e:
        return {"status": "error", "detail": f"{e.__class__.__name__}: {e}"}


async def audit(limit: int | None = None) -> dict:
    db = get_db()
    query = db["schemes"].find({}, {"schemeCode": 1, "name": 1, "applyUrl": 1, "state": 1})
    if limit:
        query = query.limit(limit)
    schemes = await query.to_list(length=limit or None)

    results = {"ok": [], "broken": [], "missing": []}
    async with httpx.AsyncClient() as client:
        for i, s in enumerate(schemes):
            url = s.get("applyUrl")
            outcome = await _check_url(client, url)
            entry = {
                "schemeCode": s.get("schemeCode"),
                "name": s.get("name"),
                "state": s.get("state"),
                "applyUrl": url,
                **outcome,
            }
            if outcome["status"] == "missing":
                results["missing"].append(entry)
            elif outcome["status"] == "ok":
                results["ok"].append(entry)
            else:
                results["broken"].append(entry)

            if (i + 1) % 25 == 0:
                logger.info("Checked %d/%d schemes (%d broken so far)", i + 1, len(schemes), len(results["broken"]))
            await asyncio.sleep(RATE_LIMIT_SECONDS)

    summary = {
        "total_checked": len(schemes),
        "ok": len(results["ok"]),
        "broken": len(results["broken"]),
        "missing_applyUrl": len(results["missing"]),
    }
    logger.info("Audit complete: %s", summary)
    return {"summary": summary, **results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only check the first N schemes (omit for full catalogue)")
    parser.add_argument("--out", type=str, default=str(Path(__file__).parent / "apply_url_audit_report.json"))
    args = parser.parse_args()

    report = asyncio.run(audit(limit=args.limit))
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nReport written to {args.out}")
    print(json.dumps(report["summary"], indent=2))
