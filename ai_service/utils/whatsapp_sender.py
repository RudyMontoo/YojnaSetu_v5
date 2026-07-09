"""
whatsapp_sender.py — Agent 6's outbound WhatsApp channel (Twilio).

Same posture as Spring Boot's OtpService dev fallback: fully functional
WITHOUT a live account. If the Twilio credentials aren't configured (they
need Twilio WhatsApp Business approval — a 1-4 week external process), every
send runs in DRY-RUN: the message is composed, logged (PII-masked), and
recorded to nudge_log exactly as a real send would be, but nothing leaves the
box. The moment TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_WHATSAPP_FROM
are set, the same code path sends for real — no other change needed.

This lets Agent 6 be built and verified end-to-end now (selection, dedup,
opt-out, templating, logging) with only the final delivery hop gated on the
external approval, instead of blocking the whole agent on Twilio.

Security: the `twilio` package is imported lazily inside the real-send branch
so it's not a hard dependency for dry-run/dev, and phone numbers are masked in
all log lines (CLAUDE.md rule #8: no PII in logs).
"""
import logging
import os

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    p = (phone or "").strip()
    return (p[:3] + "****" + p[-2:]) if len(p) >= 6 else "****"


def _twilio_config() -> dict | None:
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    sender = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()  # e.g. "whatsapp:+14155238886"
    if sid and token and sender:
        return {"sid": sid, "token": token, "from": sender}
    return None


def is_live() -> bool:
    """True only when Twilio WhatsApp is fully configured — lets callers and
    /agents/nudge/status report honestly whether nudges actually deliver."""
    return _twilio_config() is not None


async def send_whatsapp(to_phone: str, body: str) -> dict:
    """Sends one WhatsApp message, or dry-runs if Twilio isn't configured.
    Returns {status: sent|dry_run|failed|no_contact, delivered: bool, ...}.
    Never raises — a delivery failure must not crash the nudge batch."""
    if not to_phone:
        logger.info("[NUDGE] no contact number — skipping send")
        return {"status": "no_contact", "delivered": False}

    cfg = _twilio_config()
    if cfg is None:
        logger.info("[NUDGE dry-run] would send to %s: %s", _mask_phone(to_phone), body[:80])
        return {"status": "dry_run", "delivered": False}

    to = to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
    try:
        from twilio.rest import Client  # lazy: not needed for dry-run/dev
        client = Client(cfg["sid"], cfg["token"])
        # Twilio's SDK is sync; run it off the event loop.
        import asyncio
        msg = await asyncio.to_thread(
            client.messages.create, body=body, from_=cfg["from"], to=to
        )
        logger.info("[NUDGE] sent to %s (sid=%s)", _mask_phone(to_phone), msg.sid)
        return {"status": "sent", "delivered": True, "sid": msg.sid}
    except Exception as e:  # noqa: BLE001 — delivery failure must not break the batch
        logger.warning("[NUDGE] send to %s failed: %s: %s", _mask_phone(to_phone), e.__class__.__name__, e)
        return {"status": "failed", "delivered": False, "error": str(e)}
