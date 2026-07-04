"""
profile_learner.py — makes chat *teach* the citizen profile.

When a citizen says "main UP ka kisan hoon, income 1 lakh", those facts
previously lived and died inside that one turn — the next session started
blank again. This module extracts explicitly-stated profile facts from the
message, writes them to the citizen profile via Spring Boot's internal
PATCH (which creates the profile if missing and recalculates
profileCompleteness), and records them in conversation_sessions.profileUpdates
per the CLAUDE.md schema.

Runs fire-and-forget after the reply is already sent (chat_turn schedules
it with asyncio.create_task), so it never adds latency to a turn and its
failure never breaks chat. Extraction uses prefer="groq" to keep the
Gemini free-tier quota for the interactive compose calls.

Trust rules:
  - Only facts the citizen explicitly stated — the prompt forbids guessing,
    and every field is validated against a whitelist/range here before any
    write. An LLM hallucination that survives validation can at worst set a
    plausible enum value; it can never invent a new field (whitelist) or
    write PII (name/dob/phone are not extraction targets by design).
  - Values equal to the current profile are dropped (no writes, no audit
    noise, when nothing new was said).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ai_service.graph.llm import ainvoke_with_fallback
from ai_service.utils.pii_masker import mask_pii
from ai_service.utils.spring_client import patch_citizen_profile

logger = logging.getLogger(__name__)

# Intents whose messages actually carry situation facts. small_talk and
# status_check don't; grievance is usually about an application, not the person.
LEARNABLE_INTENTS = {"eligibility_query", "financial_plan", "application_request"}

_STATE_CODES = {
    "AP", "AR", "AS", "BR", "CG", "GA", "GJ", "HR", "HP", "JH", "KA", "KL",
    "MP", "MH", "MN", "ML", "MZ", "NL", "OD", "PB", "RJ", "SK", "TN", "TS",
    "TR", "UP", "UK", "WB", "AN", "CH", "DN", "DL", "JK", "LA", "LD", "PY",
}
_CATEGORIES = {"general", "obc", "sc", "st"}
_OCCUPATIONS = {"farmer", "student", "daily_wage", "self_employed", "unemployed"}
_GENDERS = {"male", "female", "other"}

_EXTRACT_PROMPT = """Extract profile facts the citizen EXPLICITLY states about themselves in this message. Do not guess or infer anything not directly said.

Message (Hindi/Hinglish/English): "{message}"

Return ONLY a JSON object with any of these keys (omit a key entirely if that fact is not stated):
- state: 2-char Indian state code (UP=Uttar Pradesh, MH=Maharashtra, BR=Bihar, RJ=Rajasthan, TN=Tamil Nadu, WB=West Bengal, MP=Madhya Pradesh, GJ=Gujarat, KA=Karnataka, DL=Delhi, ...)
- district: district name in English
- occupation: one of farmer|student|daily_wage|self_employed|unemployed
- annualIncome: yearly income in rupees as a number (convert lakh/crore: 1 lakh = 100000)
- category: one of general|obc|sc|st
- gender: one of male|female|other
- isBpl: true/false (only if BPL card / garibi rekha explicitly mentioned)
- isRural: true/false (only if village/gaon or city explicitly mentioned)
- isDisabled: true/false (only if disability explicitly mentioned)
- familySize: number of family members
- hasLand: true/false (only if owning/not owning land explicitly mentioned)
- landAreaAcres: land area in acres (convert: 1 hectare = 2.47 acres, 1 bigha ≈ 0.62 acres)

If no facts are stated, return {{}}."""


def _validated(raw: dict) -> dict:
    """Whitelist + type/range check every extracted field. Silently drops
    anything malformed — a lost fact is fine, a corrupt profile is not."""
    out = {}
    if isinstance(raw.get("state"), str) and raw["state"].strip().upper() in _STATE_CODES:
        out["state"] = raw["state"].strip().upper()
    if isinstance(raw.get("district"), str) and 0 < len(raw["district"].strip()) <= 40:
        out["district"] = raw["district"].strip().title()
    if isinstance(raw.get("occupation"), str) and raw["occupation"].strip().lower() in _OCCUPATIONS:
        out["occupation"] = raw["occupation"].strip().lower()
    if isinstance(raw.get("category"), str) and raw["category"].strip().lower() in _CATEGORIES:
        out["category"] = raw["category"].strip().lower()
    if isinstance(raw.get("gender"), str) and raw["gender"].strip().lower() in _GENDERS:
        out["gender"] = raw["gender"].strip().lower()
    if isinstance(raw.get("annualIncome"), (int, float)) and 0 < raw["annualIncome"] <= 100_000_000:
        out["annualIncome"] = int(raw["annualIncome"])
    if isinstance(raw.get("familySize"), int) and 1 <= raw["familySize"] <= 30:
        out["familySize"] = raw["familySize"]
    if isinstance(raw.get("landAreaAcres"), (int, float)) and 0 < raw["landAreaAcres"] <= 10_000:
        out["landAreaAcres"] = float(raw["landAreaAcres"])
    for flag in ("isBpl", "isRural", "isDisabled", "hasLand"):
        if isinstance(raw.get(flag), bool):
            out[flag] = raw[flag]
    return out


async def learn_profile_from_message(
    db: AsyncIOMotorDatabase,
    *,
    citizen_id: str,
    session_id: str,
    message: str,
    current_profile: dict,
) -> dict:
    """Extract → validate → diff against current profile → PATCH Spring Boot
    → record in conversation_sessions.profileUpdates. Returns the updates
    written ({} if nothing new). Never raises."""
    try:
        masked, _ = mask_pii(message)
        response = await ainvoke_with_fallback(
            _EXTRACT_PROMPT.format(message=masked), temperature=0.0, prefer="groq"
        )
        raw = response.content.strip().strip("`").removeprefix("json").strip()
        extracted = _validated(json.loads(raw))
    except Exception as e:
        logger.warning("profile extraction failed (non-fatal): %s: %s", e.__class__.__name__, e)
        return {}

    updates = {
        k: v for k, v in extracted.items()
        if (current_profile or {}).get(k) != v
    }
    if not updates:
        return {}

    if not await patch_citizen_profile(citizen_id, updates):
        return {}

    try:
        await db["conversation_sessions"].update_one(
            {"sessionId": session_id},
            {"$set": {
                **{f"profileUpdates.{k}": v for k, v in updates.items()},
                "profileUpdatedAt": datetime.now(timezone.utc),
            }},
        )
    except Exception as e:
        logger.warning("profileUpdates session write failed (non-fatal): %s", e)

    logger.info("[PROFILE-LEARN] citizen %s learned %s from chat", citizen_id, sorted(updates))
    return updates


def schedule_profile_learning(db, *, citizen_id, session_id, message, intent, current_profile):
    """Fire-and-forget hook for chat_turn — reply latency must never pay for
    profile learning. No-op for intents that don't carry situation facts."""
    if intent not in LEARNABLE_INTENTS:
        return
    task = asyncio.create_task(learn_profile_from_message(
        db, citizen_id=citizen_id, session_id=session_id,
        message=message, current_profile=current_profile,
    ))
    # keep a reference so the task isn't garbage-collected mid-flight
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


_background_tasks: set = set()
