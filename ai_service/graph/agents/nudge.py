"""
nudge.py — Agent 6 (Nudge). Per CLAUDE.md: scheduled Cloud Run job, daily
8AM + weekly Mon 9AM IST, sends WhatsApp reminders. This is the batch brain;
the delivery hop is utils/whatsapp_sender (dry-run until Twilio is approved).

What it does today, end-to-end and verifiable WITHOUT Twilio:
- Selects citizens with an actionable state — currently applications stuck at
  "saved" for > STUCK_SAVED_DAYS (they started applying and stopped). This is
  the highest-signal nudge: a warm reminder to finish something they began.
- Respects opt-out: a citizen with users.nudgeOptedOut == true is never nudged
  (DPDP-friendly; the opt-out endpoint sets it).
- Dedups: never re-nudges the same (citizen, scheme, type) within
  NUDGE_DEDUP_DAYS, so a stuck application doesn't nag daily.
- Composes a short Hinglish message and "sends" it (dry-run logs + records).
- Records every attempt to nudge_log (CLAUDE.md schema: citizen_id,
  message_type, scheme_id, sent_at, delivered, replied) — TTL 90 days.

Phone numbers are encrypted at rest and ai_service has no decryption key, so
the recipient number is fetched from Spring Boot's internal profile endpoint
(server-side decrypt) via spring_client — best-effort; a citizen with no
resolvable contact is logged as no_contact, not a crash.
"""
import logging
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.utils.spring_client import fetch_citizen_profile
from ai_service.utils.whatsapp_sender import send_whatsapp

logger = logging.getLogger(__name__)

STUCK_SAVED_DAYS = 3      # a "saved" application older than this earns a completion nudge
NUDGE_DEDUP_DAYS = 7      # don't re-nudge the same citizen+scheme+type within this window
MAX_BATCH = 200           # bound one run (CLAUDE.md: 10-min job budget)

MESSAGE_TYPE_APPLICATION_REMINDER = "application_reminder"


def _compose_reminder(scheme_name: str) -> str:
    name = scheme_name or "ek sarkari yojana"
    return (
        f"🙏 Namaste! Aapne *{name}* ke liye application shuru ki thi lekin abhi tak "
        f"complete nahi hui. Ise poora karne mein sirf kuch minute lagenge — Yojna Setu "
        f"app kholein aur 'Applications' mein jaakar aage badhein. Madad chahiye toh "
        f"reply karein. (Aap 'STOP' bhejkar ya app mein opt-out karke ye reminders band kar sakte hain.)"
    )


async def _recently_nudged(db, citizen_id: str, scheme_id, message_type: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=NUDGE_DEDUP_DAYS)
    existing = await db["nudge_log"].find_one({
        "citizen_id": citizen_id,
        "scheme_id": scheme_id,
        "message_type": message_type,
        "sent_at": {"$gte": cutoff},
    })
    return existing is not None


async def _is_opted_out(db, citizen_id: str) -> bool:
    from bson import ObjectId
    from bson.errors import InvalidId
    try:
        query = {"_id": ObjectId(citizen_id)}
    except (InvalidId, TypeError):
        query = {"_id": citizen_id}  # test/non-ObjectId ids
    user = await db["users"].find_one(query, {"nudgeOptedOut": 1})
    return bool(user and user.get("nudgeOptedOut"))


async def run_nudge_batch(db: AsyncIOMotorDatabase, *, dry_run: bool = True, limit: int = MAX_BATCH) -> dict:
    """Selects and sends application-reminder nudges. dry_run defaults True —
    the caller (admin trigger) opts into real sending explicitly, and even then
    delivery only happens if Twilio is configured (else it stays a dry-run per
    whatsapp_sender). Returns a summary of what happened."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=STUCK_SAVED_DAYS)
    cursor = (
        db["applications"]
        .find({"status": "saved", "appliedAt": {"$lte": cutoff}},
              {"userId": 1, "schemeId": 1, "schemeName": 1})
        .sort("appliedAt", 1)
        .limit(limit)
    )
    candidates = await cursor.to_list(length=limit)

    summary = {
        "candidates": len(candidates), "sent": 0, "dry_run_count": 0,
        "skipped_optout": 0, "skipped_dedup": 0, "no_contact": 0, "failed": 0,
        "live_delivery": not dry_run,
    }
    seen_citizens: set[str] = set()

    for app in candidates:
        citizen_id = app.get("userId")
        if not citizen_id or citizen_id in seen_citizens:
            continue  # one nudge per citizen per batch
        seen_citizens.add(citizen_id)

        if await _is_opted_out(db, citizen_id):
            summary["skipped_optout"] += 1
            continue
        if await _recently_nudged(db, citizen_id, app.get("schemeId"), MESSAGE_TYPE_APPLICATION_REMINDER):
            summary["skipped_dedup"] += 1
            continue

        body = _compose_reminder(app.get("schemeName"))
        profile = await fetch_citizen_profile(citizen_id)
        phone = (profile.get("phone") or "").strip()

        if dry_run:
            result = {"status": "dry_run", "delivered": False} if phone else {"status": "no_contact", "delivered": False}
            if phone:
                logger.info("[NUDGE dry-run] citizen=%s scheme=%s", citizen_id, app.get("schemeName"))
        else:
            result = await send_whatsapp(phone, body)

        # record every attempt (CLAUDE.md nudge_log schema)
        await db["nudge_log"].insert_one({
            "citizen_id": citizen_id,
            "message_type": MESSAGE_TYPE_APPLICATION_REMINDER,
            "scheme_id": app.get("schemeId"),
            "scheme_name": app.get("schemeName"),
            "sent_at": datetime.now(timezone.utc),
            "delivered": result.get("delivered", False),
            "replied": False,
            "channel_status": result.get("status"),
        })

        status = result.get("status")
        if status == "sent":
            summary["sent"] += 1
        elif status == "dry_run":
            summary["dry_run_count"] += 1
        elif status == "no_contact":
            summary["no_contact"] += 1
        elif status == "failed":
            summary["failed"] += 1

    logger.info("[NUDGE] batch done: %s", summary)
    return summary
