"""
Unit coverage for Agent 6's dry-run-safe pieces (utils/whatsapp_sender.py,
graph/agents/nudge.py message composition). Self-contained: no Twilio, no
Mongo, no network — the sender's dry-run branch needs none of them, which is
exactly the property that lets Agent 6 be built before Twilio is approved.

The full batch (selection/opt-out/dedup/nudge_log) is hand-verified against
real Mongo per session.
"""
import asyncio

from ai_service.graph.agents.nudge import _compose_email, _compose_reminder
from ai_service.utils.email_sender import _mask_email
from ai_service.utils.email_sender import is_live as email_is_live
from ai_service.utils.email_sender import send_email
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


# ── email channel (primary, no Twilio/DLT needed) ──

def test_email_is_masked_for_logs():
    # CLAUDE.md rule #8: no PII (full address) in logs
    masked = _mask_email("rudrashr27@gmail.com")
    assert masked.endswith("@gmail.com")
    assert "rudrashr27" not in masked
    assert _mask_email("nope") == "****"
    assert _mask_email("") == "****"


def test_email_is_live_false_without_smtp(monkeypatch):
    for var in ("MAIL_ENABLED", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_FROM"):
        monkeypatch.delenv(var, raising=False)
    assert email_is_live() is False


def test_email_is_live_requires_enabled_flag(monkeypatch):
    # all creds present but MAIL_ENABLED not "true" -> still not live (mirrors EmailService.java)
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.brevo.com")
    monkeypatch.setenv("SMTP_USERNAME", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("MAIL_FROM", "no-reply@yojsarthi.in")
    monkeypatch.setenv("MAIL_ENABLED", "false")
    assert email_is_live() is False
    monkeypatch.setenv("MAIL_ENABLED", "true")
    assert email_is_live() is True


def test_email_dry_runs_without_smtp(monkeypatch):
    for var in ("MAIL_ENABLED", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_FROM"):
        monkeypatch.delenv(var, raising=False)
    res = asyncio.run(send_email("a@b.com", "subj", "body"))
    assert res["status"] == "dry_run" and res["delivered"] is False


def test_email_no_contact_on_empty_address():
    res = asyncio.run(send_email("", "subj", "body"))
    assert res["status"] == "no_contact" and res["delivered"] is False


def test_email_reminder_has_subject_body_and_optout():
    subject, body = _compose_email("PM Kisan Samman Nidhi")
    assert "PM Kisan Samman Nidhi" in subject and "PM Kisan Samman Nidhi" in body
    assert "opt-out" in body.lower() or "opt out" in body.lower()
    assert "*" not in body  # plain text, not WhatsApp markup
