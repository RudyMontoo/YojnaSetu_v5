"""
Unit coverage for Agent 3's read-only portal reconnaissance
(utils/portal_recon.py). Two things must never regress:

1. The security boundary — a non-government URL is refused BEFORE any network
   call (the whitelist is the only access control, per CLAUDE.md). These tests
   make no network request: the refusal happens before the fetch.
2. The HTML form parser — extracts real fields/labels/required flags from a
   static fixture, and excludes hidden/submit controls. Deterministic, offline.

The live path (fetch a real gov page) is hand-verified per session; it can't be
a CI test (needs network + a live portal).
"""
import asyncio

from bs4 import BeautifulSoup

from ai_service.utils.portal_recon import _extract_doc_hints, _extract_forms, recon_portal


# ---- security boundary (network-free: refusal is before any fetch) ----

def test_non_gov_url_refused_without_fetch():
    r = asyncio.run(recon_portal("https://example.com/apply"))
    assert r["error"] == "domain_not_allowed"
    assert r["reachable"] is False
    assert r["forms"] == []


def test_spoof_domain_refused():
    for spoof in (
        "https://pmkisan.gov.in.evil.com/form",
        "https://notgov.in/apply",
        "http://gov.in.attacker.net/",
    ):
        r = asyncio.run(recon_portal(spoof))
        assert r["error"] == "domain_not_allowed", spoof


def test_empty_url_refused():
    r = asyncio.run(recon_portal(""))
    assert r["error"] == "domain_not_allowed"


# ---- HTML form parser (offline, deterministic) ----

_SAMPLE_FORM = """
<html><body>
<form action="/submit" method="post">
  <label for="aadhaar">Aadhaar Number</label>
  <input type="text" id="aadhaar" name="uid" required>

  <label for="state">State</label>
  <select id="state" name="state">
    <option>Uttar Pradesh</option><option>Bihar</option>
  </select>

  <input type="text" name="mobile" placeholder="Mobile Number">
  <input type="hidden" name="__VIEWSTATE" value="xyz">
  <input type="submit" value="Apply">
</form>
</body></html>
"""


def test_extract_forms_reads_fields_labels_required():
    soup = BeautifulSoup(_SAMPLE_FORM, "lxml")
    forms = _extract_forms(soup)
    assert len(forms) == 1
    fields = forms[0]["fields"]
    by_name = {f["name"]: f for f in fields}

    # hidden + submit excluded
    assert "__VIEWSTATE" not in by_name
    assert all(f["type"] not in ("hidden", "submit") for f in fields)

    # label resolution via <label for=...>
    assert by_name["uid"]["label"] == "Aadhaar Number"
    assert by_name["uid"]["required"] is True

    # placeholder fallback when no <label>
    assert by_name["mobile"]["label"] == "Mobile Number"
    assert by_name["mobile"]["required"] is False

    # select options captured
    assert by_name["state"]["type"] == "select"
    assert "Uttar Pradesh" in by_name["state"]["options"]


def test_extract_doc_hints_finds_document_lines():
    html = """
    <ul>
      <li>Aadhaar card is required for verification</li>
      <li>Income certificate from the tehsildar</li>
      <li>Some unrelated navigation link</li>
    </ul>
    """
    hints = _extract_doc_hints(BeautifulSoup(html, "lxml"))
    assert any("Aadhaar" in h for h in hints)
    assert any("Income certificate" in h for h in hints)
