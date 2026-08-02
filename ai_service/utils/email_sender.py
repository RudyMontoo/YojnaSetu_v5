"""
email_sender.py — Agent 6's outbound EMAIL channel (SMTP / Brevo).

Same posture and env vars as Spring Boot's EmailService (the working login-OTP
mailer): if SMTP isn't configured, every send runs in DRY-RUN — composed,
logged (recipient masked), and reported exactly as a real send would be, but
nothing leaves the box. When SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/MAIL_FROM
are set and MAIL_ENABLED=true, the same path sends for real.

Why email is Agent 6's primary channel: it needs no WhatsApp Business
approval and no DLT registration (the two external walls that gate Twilio/SMS
in India), and the exact SMTP account is already proven working by the email
login OTP. WhatsApp (utils/whatsapp_sender) stays as an optional second channel
that lights up once Twilio is approved.

Security: phone-style PII rule #8 applies — the recipient address is masked in
every log line; SMTP runs off the event loop (asyncio.to_thread); a delivery
failure returns a status, never raises, so it can't break the nudge batch.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return "****"
    local, _, domain = e.partition("@")
    shown = local[:2] if len(local) >= 2 else local
    return f"{shown}***@{domain}"


def _smtp_config() -> dict | None:
    """Returns the SMTP settings only if fully configured AND enabled — mirrors
    EmailService.java's (app.mail.enabled && from && sender) gate exactly, so
    ai_service and the gateway agree on when email is 'live'."""
    if os.getenv("MAIL_ENABLED", "false").strip().lower() != "true":
        return None
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    mail_from = os.getenv("MAIL_FROM", "").strip()
    if host and user and password and mail_from:
        return {
            "host": host,
            "port": int(os.getenv("SMTP_PORT", "587") or "587"),
            "user": user,
            "password": password,
            "from": mail_from,
            "from_name": os.getenv("MAIL_FROM_NAME", "Yojna Sarthi").strip() or "Yojna Sarthi",
        }
    return None


def is_live() -> bool:
    """True only when SMTP is fully configured + enabled — lets callers and
    /agents/nudge/status report honestly whether nudges actually deliver."""
    return _smtp_config() is not None


def _from_header(cfg: dict) -> str:
    # "Yojna Sarthi <no-reply@…>" unless MAIL_FROM already carries a display name.
    frm = cfg["from"]
    return frm if "<" in frm else f'{cfg["from_name"]} <{frm}>'


def _send_sync(cfg: dict, to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = _from_header(cfg)
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=20) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)


async def send_email(to_email: str, subject: str, body: str) -> dict:
    """Sends one email, or dry-runs if SMTP isn't configured/enabled.
    Returns {status: sent|dry_run|failed|no_contact, delivered: bool, ...}.
    Never raises — a delivery failure must not crash the nudge batch."""
    if not to_email:
        logger.info("[NUDGE] no email address — skipping send")
        return {"status": "no_contact", "delivered": False}

    cfg = _smtp_config()
    if cfg is None:
        logger.info("[NUDGE dry-run] would email %s: %s", _mask_email(to_email), subject)
        return {"status": "dry_run", "delivered": False}

    try:
        import asyncio
        await asyncio.to_thread(_send_sync, cfg, to_email, subject, body)
        logger.info("[NUDGE] emailed %s", _mask_email(to_email))
        return {"status": "sent", "delivered": True}
    except Exception as e:  # noqa: BLE001 — delivery failure must not break the batch
        logger.warning("[NUDGE] email to %s failed: %s: %s", _mask_email(to_email), e.__class__.__name__, e)
        return {"status": "failed", "delivered": False, "error": str(e)}
