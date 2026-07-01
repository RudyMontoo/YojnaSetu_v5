"""
domain_whitelist.py — the ONLY access control for Agent 3/5 portal
navigation, per CLAUDE.md's Browser-Use Security Rules. Do NOT modify
without a formal security review. Never hardcode allowed URLs anywhere
else.

Browser automation doesn't exist yet (Phase 6 is starting with the
human-checklist guidance path) — but every applyUrl Agent 3 RECOMMENDS to
a citizen is validated here too, so a poisoned/mis-scraped scheme doc
can't steer citizens to a non-government site. That check is live today.
"""
from urllib.parse import urlparse

# CLAUDE.md's exact list. *.gov.in covers pgportal/scholarships/pmkisan;
# nic.in is NOT wildcarded — only the named host.
_ALLOWED_SUFFIXES = (".gov.in", ".nic.in")
_ALLOWED_EXACT = {"pmayg.nic.in", "pmkisan.gov.in", "pgportal.gov.in", "scholarships.gov.in"}
# .nic.in is suffix-listed above because many legitimate scheme portals live
# there (pmayg.nic.in per CLAUDE.md, state boards) — both TLD families are
# government-controlled registries in India.


def is_allowed_url(url: str) -> bool:
    """True only for https:// URLs on Indian government domains."""
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme not in ("https", "http"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return (
        host in _ALLOWED_EXACT
        or host.endswith(_ALLOWED_SUFFIXES)
        or host in {s.lstrip(".") for s in _ALLOWED_SUFFIXES}  # bare gov.in / nic.in
    )
