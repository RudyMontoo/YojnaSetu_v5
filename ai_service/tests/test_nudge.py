"""
Unit coverage for Agent 6's dry-run-safe pieces (utils/whatsapp_sender.py,
graph/agents/nudge.py message composition). Self-contained: no Twilio, no
Mongo, no network — the sender's dry-run branch needs none of them, which is
exactly the property that lets Agent 6 be built before Twilio is approved.

The full batch (selection/opt-out/dedup/nudge_log) is hand-verified against
real Mongo per session.
"""
import asyncio

from ai_service.graph.agents.nudge import _compose_reminder
from ai_service.utils.whatsapp_sender import _mask_phone, is_live, send_whatsapp


def test_phone_is_masked_for_logs():
    # CLAUDE.md rule #8: no PII (full phone) in logs
    masked = _mask_phone("+919812345678")
    assert masked.startswith("+91") and masked.endswith("78")
    assert "9812345" not in masked
    assert _mask_phone("123") == "****"
    assert _mask_phone("") == "****"


def test_is_live_false_without_credentials(monkeypatch):
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"):
        monkeypatch.delenv(var, raising=False)
    assert is_live() is False


def test_send_dry_runs_without_credentials(monkeypatch):
    for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"):
        monkeypatch.delenv(var, raising=False)
    res = asyncio.run(send_whatsapp("+919812345678", "hello"))
    assert res["status"] == "dry_run" and res["delivered"] is False


def test_send_no_contact_on_empty_phone():
    res = asyncio.run(send_whatsapp("", "hello"))
    assert res["status"] == "no_contact" and res["delivered"] is False


def test_reminder_names_scheme_and_offers_optout():
    msg = _compose_reminder("PM Kisan Samman Nidhi")
    assert "PM Kisan Samman Nidhi" in msg
    # must give the citizen a way out (DPDP / anti-spam)
    assert "opt-out" in msg.lower() or "stop" in msg.lower()


def test_reminder_handles_missing_scheme_name():
    msg = _compose_reminder("")
    assert "yojana" in msg.lower()  # graceful generic fallback, no empty bold
