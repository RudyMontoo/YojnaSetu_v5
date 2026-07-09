"""
portal_recon.py — Agent 3's read-only "live portal reconnaissance".

The guidance path (graph/agents/application_guidance.py) already tells a
citizen HOW to apply from curated playbooks + grounded LLM steps. This module
adds a live, read-only look at what the government application page ACTUALLY
asks for right now — the visible form fields, required documents, and section
headings — so guidance can reflect the real current form instead of only a
static playbook.

Deliberate scope (see the Agent 3 decision, 2026-07-09):
- READ ONLY. It performs a plain HTTP GET and parses the returned HTML. It
  never fills a field, never submits, never logs in, never stores a
  credential. Auto-fill/submit on real gov portals needs the citizen's own
  login/Aadhaar/OTP that a bot can't hold, and can't be verified without
  filing a real application — explicitly out of scope.
- Government domains ONLY. Every URL — the requested one AND every redirect
  hop — is checked against utils/domain_whitelist.is_allowed_url(). A redirect
  that leaves *.gov.in / *.nic.in aborts the recon (a redirect must not be a
  whitelist bypass). This is the same hard boundary CLAUDE.md mandates for
  browser navigation.
- Honest identification: the project's real bot User-Agent, no browser
  masquerading (matches the pipeline scrapers' rule).

Graceful by contract: any failure (blocked domain, timeout, non-HTML, a
JS-only SPA with no server-rendered form) returns a structured result with a
`note`/`error`, never raises — the caller falls back to the static playbook.
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ai_service.utils.domain_whitelist import is_allowed_url

logger = logging.getLogger(__name__)

# Honest bot identity — same posture as the discovery scrapers (CLAUDE.md).
USER_AGENT = "YojnaSetu-Bot/1.0 (student project; contact: rudra@yojnasetu.in)"

MAX_REDIRECTS = 5
MAX_BYTES = 3 * 1024 * 1024      # don't parse a runaway response
TIMEOUT_SECONDS = 15.0
MAX_FIELDS = 60                   # bound the returned structure
MAX_HEADINGS = 25

# Words that flag a "documents required" section worth surfacing to the citizen.
_DOC_HINT_WORDS = ("document", "certificate", "aadhaar", "aadhar", "proof", "required", "upload")


def _field_label(inp, label_map: dict[str, str]) -> str:
    """Best-effort human label for an input: <label for=id>, then aria-label,
    then placeholder, then the name attribute."""
    _id = inp.get("id")
    if _id and _id in label_map:
        return label_map[_id]
    for attr in ("aria-label", "placeholder", "title"):
        if inp.get(attr):
            return inp[attr].strip()
    return (inp.get("name") or "").strip()


def _extract_forms(soup: BeautifulSoup) -> list[dict]:
    # id -> label text, for resolving <label for=...>
    label_map = {
        lbl["for"]: lbl.get_text(" ", strip=True)
        for lbl in soup.find_all("label")
        if lbl.get("for")
    }
    forms = []
    field_budget = MAX_FIELDS
    for form in soup.find_all("form"):
        fields = []
        for el in form.find_all(["input", "select", "textarea"]):
            if field_budget <= 0:
                break
            etype = el.get("type", el.name)
            if etype in ("hidden", "submit", "button", "image", "reset"):
                continue
            field = {
                "label": _field_label(el, label_map) or "(unlabeled)",
                "name": (el.get("name") or "").strip(),
                "type": etype,
                "required": el.has_attr("required") or el.get("aria-required") == "true",
            }
            if el.name == "select":
                opts = [o.get_text(strip=True) for o in el.find_all("option") if o.get_text(strip=True)]
                if opts:
                    field["options"] = opts[:15]
            fields.append(field)
            field_budget -= 1
        if fields:
            forms.append({
                "action": (form.get("action") or "").strip(),
                "method": (form.get("method") or "get").lower(),
                "fields": fields,
            })
    return forms


def _extract_doc_hints(soup: BeautifulSoup) -> list[str]:
    hints = []
    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        if 8 <= len(text) <= 160 and any(w in text.lower() for w in _DOC_HINT_WORDS):
            hints.append(text)
        if len(hints) >= 20:
            break
    return hints


async def recon_portal(url: str, *, timeout: float = TIMEOUT_SECONDS) -> dict:
    """Fetch a whitelisted government application page (read-only) and return
    its live form structure. Never raises — failures come back as a result
    with `error`/`note` set so the caller can fall back to static guidance."""
    result: dict = {
        "requested_url": url,
        "final_url": None,
        "reachable": False,
        "status_code": None,
        "forms": [],
        "document_hints": [],
        "headings": [],
        "note": None,
        "error": None,
    }

    if not is_allowed_url(url):
        result["error"] = "domain_not_allowed"
        result["note"] = "URL is not on an Indian government domain (*.gov.in / *.nic.in); recon refused."
        return result

    try:
        async with httpx.AsyncClient(
            follow_redirects=False,  # follow manually so each hop is re-checked against the whitelist
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            current = url
            for _ in range(MAX_REDIRECTS + 1):
                resp = await client.get(current)
                if resp.is_redirect:
                    location = resp.headers.get("location", "")
                    nxt = urljoin(current, location)
                    if not is_allowed_url(nxt):
                        result["error"] = "redirect_off_whitelist"
                        result["note"] = f"Portal redirected off government domains ({urlparse(nxt).hostname}); recon aborted."
                        return result
                    current = nxt
                    continue
                break
            else:
                result["error"] = "too_many_redirects"
                return result

            result["final_url"] = str(resp.url)
            result["status_code"] = resp.status_code
            result["reachable"] = resp.status_code < 400

            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype.lower():
                result["note"] = f"Portal returned non-HTML content ({ctype or 'unknown'}); no form to read."
                return result

            body = resp.content[:MAX_BYTES]
    except (httpx.HTTPError, httpx.InvalidURL) as e:
        result["error"] = e.__class__.__name__
        result["note"] = "Could not reach the government portal right now; use the step-by-step guidance instead."
        logger.info("portal_recon failed for %s: %s", url, e)
        return result

    soup = BeautifulSoup(body, "lxml")
    result["forms"] = _extract_forms(soup)
    result["document_hints"] = _extract_doc_hints(soup)
    result["headings"] = [
        h.get_text(" ", strip=True)
        for h in soup.find_all(["h1", "h2", "h3"])
        if h.get_text(strip=True)
    ][:MAX_HEADINGS]

    if not result["forms"]:
        result["note"] = (
            "No server-rendered application form was found — this portal is likely "
            "JavaScript-rendered, so its fields can't be read without a full browser. "
            "The step-by-step guidance still applies."
        )
    return result
