"""
Unit coverage for the status_check node's grounding logic (graph/agents/
status_check.py). Pure-function level — no Mongo, no LLM, no network — so it
runs in CI anywhere, same contract as the rest of ai_service/tests/.

The end-to-end path (real applications in Mongo -> grounded reply) is
hand-verified per session; what's pinned here is the part that must never
regress: the status -> Hinglish mapping stays exhaustive and honest, and the
deterministic composer never invents a status the data doesn't carry.
"""
from ai_service.graph.agents.status_check import (
    _STATUS_HINGLISH,
    _compose_deterministic,
    _status_line,
)


def test_all_documented_statuses_have_hinglish():
    # Mirrors Application.java's documented status set. If Spring adds a status,
    # this test forces a matching citizen-facing phrase (else it falls back to
    # the raw machine value, which is ugly but not wrong).
    documented = {"saved", "in_progress", "submitted", "approved", "rejected", "disbursed"}
    assert documented <= set(_STATUS_HINGLISH)


def test_status_line_uses_scheme_name_and_surfaces_ref():
    app = {"schemeName": "PM Kisan", "status": "submitted", "externalAppId": "PMK-1"}
    line = _status_line(app)
    assert "PM Kisan" in line
    assert "submit" in line
    assert "PMK-1" in line  # external app id surfaced when present


def test_status_line_no_ref_when_absent():
    line = _status_line({"schemeName": "Ayushman", "status": "saved"})
    assert "ref:" not in line


def test_status_line_falls_back_to_code_then_raw_status():
    # unknown status must degrade to itself, not silently drop or mislabel
    line = _status_line({"schemeCode": "XYZ", "status": "on_hold"})
    assert "XYZ" in line
    assert "on_hold" in line


def test_status_line_defaults_missing_status_to_saved():
    line = _status_line({"schemeName": "Scheme A"})
    assert _STATUS_HINGLISH["saved"] in line


def test_compose_empty_is_honest_not_error():
    reply = _compose_deterministic([])
    assert "koi application" in reply
    # must not fabricate any status word for a citizen with no applications
    assert not any(w in reply for w in ("submit ho chuki", "approve ho gayi", "reject ho gayi"))


def test_compose_lists_every_application_and_pluralizes():
    apps = [
        {"schemeName": "A", "status": "saved"},
        {"schemeName": "B", "status": "approved"},
    ]
    reply = _compose_deterministic(apps)
    assert "A" in reply and "B" in reply
    assert "2 applications" in reply


def test_compose_singular_grammar():
    reply = _compose_deterministic([{"schemeName": "Solo", "status": "submitted"}])
    assert "1 application" in reply and "1 applications" not in reply


def test_compose_never_claims_disbursed_unless_present():
    apps = [{"schemeName": "A", "status": "submitted"}]
    reply = _compose_deterministic(apps)
    assert _STATUS_HINGLISH["disbursed"] not in reply
