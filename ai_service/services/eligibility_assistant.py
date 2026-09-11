"""
eligibility_assistant.py — conversational intake for "what am I eligible for?",
as opposed to application_assistant.py's "fill in my application for scheme X".

Why this exists as its own module rather than a form: the citizen this SIH
problem statement is for does not know NSFDC's scheme taxonomy — "unit cost
ceiling", "margin money", which of 6 near-identical schemes applies to them.
A dropdown form still asks them to know what to look for; a conversation lets
them say "I want to open a tea shop, I don't have much money" and have THAT
translated into the fields the real eligibility engine needs. The static
scheme-browsing pages already exist and cover the citizen who already knows
what they're looking for — this covers the one who doesn't.

The one hard rule, non-negotiable given this project's own history (the P0
bug: the old UI quoted a unit-cost ceiling as the loan cap): this module
NEVER answers "you qualify for X" from its own reasoning. It only extracts
structured facts from what the citizen said — same two-layer approach as
application_assistant.py (deterministic regex first, LLM only for what regex
missed, LLM never overrides a deterministic hit) — then calls the real
CreditEligibilityService via spring_client.check_credit_eligibility() and
relays its actual verdict. If that call fails, the honest answer is "couldn't
check right now", never a guess.

Stateless by design: unlike application_assistant (authenticated, session
persisted server-side in conversation_sessions), this runs for guests with no
account and no cookie — matching the credit module's public-by-design
eligibility check. The caller (frontend) holds `context` between turns and
sends it back each request; nothing is written to Mongo. That also means no
citizen data is retained anywhere unless they later create an account and
choose to save it — the same "nothing is saved unless you ask us to" promise
the plain-form EligibilityPage already made.
"""
import logging
import re
from typing import Any

from ai_service.graph.llm import ainvoke_with_fallback, language_instruction
from ai_service.services.application_assistant import (
    _AMOUNT_RE, _CATEGORY_MAP, _GENDER_MAP, _INCOME_KEYWORDS, _COST_KEYWORDS,
    _to_number,
)
from ai_service.utils.spring_client import check_credit_eligibility

logger = logging.getLogger(__name__)

REQUIRED_SLOTS = ["need", "estimatedCost", "annualIncome"]
# Asked once, as a single extra round, then the check proceeds regardless of
# whether they're answered — insufficient_data is an honest verdict state the
# real API already supports, not something this chat needs to block on.
OPTIONAL_SLOTS = ["category", "gender"]

_NEED_BUSINESS_RE = re.compile(
    r"business|shop|dukaan|trade|self[-\s]?employ|vyapar|vyavsay|startup|"
    r"petty trade|tea|candle|papad|goat|parlour|parlor|enterprise",
    re.IGNORECASE,
)
_NEED_EDUCATION_RE = re.compile(
    r"education|college|course|study|padhai|padhna|fees?\b|degree|tuition|"
    r"hostel|school|university|admission",
    re.IGNORECASE,
)

SLOT_ASK: dict[str, dict[str, str]] = {
    "need": {
        "en": "What's this loan for — a business you're starting or running, or education (a course, tuition, hostel)?",
        "hi": "Yeh loan kis liye hai — koi business, ya padhai (course, tuition, hostel)?",
    },
    "estimatedCost": {
        "en": "Roughly how much will it cost in total — the full project or course cost, not what you want to borrow?",
        "hi": "Total kharcha kitna hoga (poora project ya course cost, jitna udhaar lena hai woh nahi)?",
    },
    "annualIncome": {
        "en": "What's your annual family income — everyone earning in the household, over a year?",
        "hi": "Aapke poore parivar ki saalana income kitni hai?",
    },
    "category_gender": {
        "en": "Two quick ones, only if you know: your social category (SC/ST/OBC/general), and is this application for a woman? Some schemes are women-only with a lower rate.",
        "hi": "Do aur baatein, agar pata ho: aapki category (SC/ST/OBC/general), aur kya yeh mahila ke liye hai? Kuch schemes sirf mahilaon ke liye kam byaj par hain.",
    },
}
_CHECKING = {
    "en": "Thanks — checking real scheme figures for you now…",
    "hi": "Dhanyawad — ab main aapke liye asli scheme figures check kar raha hoon…",
}
_CHECK_FAILED = {
    "en": "I couldn't reach the eligibility check just now — please try again in a moment.",
    "hi": "Abhi eligibility check nahi ho paaya — thodi der mein dobara try karein.",
}
_DEFAULT_LANG = "en"


def extract_slots_deterministic(text: str) -> dict[str, Any]:
    """Same regex-first, no-guessing approach as application_assistant.py's
    version, extended with `need` detection. Reuses that module's amount/
    category/gender patterns directly rather than re-deriving them — one
    tested implementation, not two that can drift apart."""
    if not text:
        return {}
    slots: dict[str, Any] = {}

    for keyword_re, key in ((_COST_KEYWORDS, "estimatedCost"), (_INCOME_KEYWORDS, "annualIncome")):
        for m in keyword_re.finditer(text):
            window = text[m.end(): m.end() + 40]
            amount_m = _AMOUNT_RE.search(window)
            if amount_m and amount_m.group(1):
                slots[key] = _to_number(amount_m.group(1), amount_m.group(2))
                break

    if "estimatedCost" not in slots and "annualIncome" not in slots:
        amount_m = _AMOUNT_RE.search(text)
        if amount_m and amount_m.group(1) and amount_m.group(2):
            slots["_bare_amount"] = _to_number(amount_m.group(1), amount_m.group(2))

    if _NEED_BUSINESS_RE.search(text):
        slots["need"] = "business"
    elif _NEED_EDUCATION_RE.search(text):
        slots["need"] = "education"

    for value, pattern in _CATEGORY_MAP.items():
        if pattern.search(text):
            slots["category"] = value
            break
    for value, pattern in _GENDER_MAP.items():
        if pattern.search(text):
            slots["gender"] = value
            break

    return slots


class EligibilityAssistant:
    async def process_message(
        self, user_text: str, language: str, context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        context: {slots, missing_required, asked_optional} — {} on a fresh chat.
        Returns {"bot_reply": str, "context": dict, "results": dict | None}.
        `results` is the real EligibilityResponse (verdict/recommendations/
        missingProfileData/note) once enough has been collected — never chat
        prose standing in for it.
        """
        context = self._normalize(context)
        lang = (language or "").strip().lower()

        await self._merge_slots(user_text, context)

        missing = [f for f in REQUIRED_SLOTS if context["slots"].get(f) is None]
        context["missing_required"] = missing

        if missing:
            return {
                "bot_reply": await self._ask_for_slots(missing, lang, context),
                "context": context,
                "results": None,
            }

        if not context["asked_optional"]:
            context["asked_optional"] = True
            still_want = [f for f in OPTIONAL_SLOTS if context["slots"].get(f) is None]
            if still_want:
                prompt = SLOT_ASK["category_gender"].get(lang, SLOT_ASK["category_gender"][_DEFAULT_LANG])
                return {"bot_reply": prompt, "context": context, "results": None}

        results = await check_credit_eligibility({
            "need": context["slots"]["need"],
            "estimatedCost": context["slots"]["estimatedCost"],
            "annualIncome": context["slots"].get("annualIncome"),
            "category": context["slots"].get("category"),
            "gender": context["slots"].get("gender"),
        })
        if results is None:
            return {
                "bot_reply": _CHECK_FAILED.get(lang, _CHECK_FAILED[_DEFAULT_LANG]),
                "context": context,
                "results": None,
            }
        return {
            "bot_reply": _CHECKING.get(lang, _CHECKING[_DEFAULT_LANG]),
            "context": context,
            "results": results,
        }

    @staticmethod
    def _normalize(context: dict[str, Any]) -> dict[str, Any]:
        context = dict(context or {})
        context["slots"] = dict(context.get("slots") or {})
        context.setdefault("missing_required", list(REQUIRED_SLOTS))
        context.setdefault("asked_optional", False)
        return context

    async def _merge_slots(self, user_text: str, context: dict) -> None:
        deterministic = extract_slots_deterministic(user_text)
        bare_amount = deterministic.pop("_bare_amount", None)

        still_missing = [f for f in ("estimatedCost", "annualIncome") if context["slots"].get(f) is None]
        if bare_amount is not None and len(still_missing) == 1:
            deterministic[still_missing[0]] = bare_amount

        for key, value in deterministic.items():
            context["slots"][key] = value

        still_open = [f for f in (REQUIRED_SLOTS + OPTIONAL_SLOTS) if context["slots"].get(f) is None]
        if still_open:
            llm_extracted = await self._extract_slots_llm(user_text)
            for key in still_open:
                if llm_extracted.get(key) is not None:
                    context["slots"][key] = llm_extracted[key]

    async def _extract_slots_llm(self, user_text: str) -> dict[str, Any]:
        prompt = f"""Extract ONLY facts explicitly stated in this message about a loan/scheme enquiry. \
Do NOT infer, estimate, or round any number that wasn't actually said — return null if not clearly stated.

Message: "{user_text}"

Return ONLY a JSON object with these keys:
{{"need": "<business or education, or null>", "estimatedCost": <number in rupees or null>, \
"annualIncome": <number in rupees or null>, "category": "<sc|st|obc|general or null>", \
"gender": "<male|female or null>"}}"""
        try:
            response = await ainvoke_with_fallback(prompt, temperature=0.0, tags=["internal"])
            return self._safe_json(response.content)
        except Exception as e:
            logger.warning("Eligibility assistant slot extraction failed: %s", e)
            return {}

    @staticmethod
    def _safe_json(raw: str) -> dict:
        import json
        try:
            cleaned = (raw or "").strip().strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    async def _ask_for_slots(self, missing: list[str], lang: str, context: dict) -> str:
        asks = [SLOT_ASK[f].get(lang, SLOT_ASK[f][_DEFAULT_LANG]) for f in missing[:1]]
        prompt = (
            f"You are Sathi, a warm assistant helping a citizen find which concessional credit "
            f"scheme they qualify for. Ask them this, in 1-2 short sentences: {asks[0]}. "
            f"{language_instruction(lang)}"
        )
        try:
            response = await ainvoke_with_fallback(prompt, temperature=0.3)
            return response.content.strip() or asks[0]
        except Exception:
            return asks[0]
