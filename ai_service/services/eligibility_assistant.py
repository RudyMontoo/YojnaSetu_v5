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

This class itself is pure: it takes a context dict in and hands one back, and
writes nothing anywhere. Persistence is the router's job, and it is no longer
"none" — routing this flow through the orchestrator means turns are stored in
conversation_sessions under an anonymous `guest:<session_id>` id, because the
orchestrator needs conversation history between turns (see
eligibility_assistant_router._guest_citizen_id).

That matters for what the UI is allowed to claim. This page used to promise
"nothing is saved unless you ask us to", which stopped being true the moment
the flow gained a session. The promise the UI now makes — and the only one
this design supports — is narrower and accurate: the conversation is stored
against a random session id, not against a person, no account is created, and
a guest has no CitizenProfile, so no agent can attach these answers to a real
identity.
"""
import logging
import re
from typing import Any

from ai_service.graph.llm import ainvoke_with_fallback, language_instruction
from ai_service.graph.quick_replies import chips_after_results, chips_for, progress
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
# annualIncome means the whole YEAR, but citizens very naturally state a
# monthly figure ("3 lakh per month") — silently storing that as-is would
# understate annual income 12x, which can flip a genuine "over the income
# cap" citizen into a false "eligible". Real bug caught live 2026-09-12:
# "₹3 lakhs per month" was stored as annualIncome=300000 unchanged.
_MONTHLY_RE = re.compile(
    r"per\s*month|/\s*month|\bmonthly\b|\bmahina\b|\bmaheene\b|\bmahine\b|\bप्रति\s*माह\b",
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


def _format_inr(n: Any) -> str:
    """Indian digit grouping (5,00,00,000 not 50,000,000) with a ₹ prefix —
    used ONLY for restating a figure back to the citizen; never for anything
    sent to the eligibility API, which takes the raw number."""
    try:
        value = int(round(float(n)))
    except (TypeError, ValueError):
        return str(n)
    sign = "-" if value < 0 else ""
    s = str(abs(value))
    if len(s) > 3:
        head, last3 = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [last3])
    return f"{sign}₹{s}"


def _format_fact(key: str, value: Any) -> str:
    """Renders one extracted slot as a short, unambiguous English clause —
    the ONLY form these facts reach the LLM in when it composes the next
    question, so a hallucinated currency/unit has nowhere to enter."""
    if key == "estimatedCost":
        return f"the total project/course cost is {_format_inr(value)}"
    if key == "annualIncome":
        return f"annual family income is {_format_inr(value)}"
    if key == "need":
        return f"this loan is for {value}"
    if key == "category":
        return f"social category is {str(value).upper()}"
    if key == "gender":
        return f"applicant gender is {value}"
    return f"{key} is {value}"


def extract_slots_deterministic(text: str) -> dict[str, Any]:
    """Same regex-first, no-guessing approach as application_assistant.py's
    version, extended with `need` detection. Reuses that module's amount/
    category/gender patterns directly rather than re-deriving them — one
    tested implementation, not two that can drift apart."""
    if not text:
        return {}
    slots: dict[str, Any] = {}

    monthly_stated = bool(_MONTHLY_RE.search(text))
    for keyword_re, key in ((_COST_KEYWORDS, "estimatedCost"), (_INCOME_KEYWORDS, "annualIncome")):
        for m in keyword_re.finditer(text):
            window = text[m.end(): m.end() + 40]
            amount_m = _AMOUNT_RE.search(window)
            if amount_m and amount_m.group(1):
                value = _to_number(amount_m.group(1), amount_m.group(2))
                # Only annualIncome gets annualized — estimatedCost is a
                # one-time project/course cost, "per month" doesn't apply.
                if key == "annualIncome" and monthly_stated:
                    value *= 12
                slots[key] = value
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
        Returns {"bot_reply", "context", "results", "quick_replies", "progress"}.
        `results` is the real EligibilityResponse (verdict/recommendations/
        missingProfileData/note) once enough has been collected — never chat
        prose standing in for it.

        `quick_replies` are tappable answers to the question just asked (see
        graph/quick_replies.py) and `progress` is {answered, total} over the
        required slots. Both are presentation aids for the SAME question the
        bot_reply asks — a client that ignores them still gets an identical,
        complete conversation through the text box.
        """
        context = self._normalize(context)
        lang = (language or "").strip().lower()

        # Snapshot before merging so _ask_for_slots can acknowledge whatever
        # this message actually added. Without this, a message that answers
        # something OTHER than the still-missing question (a citizen
        # volunteering their category before being asked, say) got the exact
        # same question re-asked with no sign it was heard — reads as a
        # scripted bot ignoring input, not a targeted follow-up.
        before = dict(context["slots"])
        await self._merge_slots(user_text, context)
        newly_filled = {k: v for k, v in context["slots"].items() if before.get(k) is None and v is not None}

        missing = [f for f in REQUIRED_SLOTS if context["slots"].get(f) is None]
        context["missing_required"] = missing

        # Computed once here and attached to every return: the chips always
        # describe the question THIS reply asks, so they can never lag a turn
        # behind the prose (which is how chip UIs usually go wrong).
        bar = progress(context["slots"], REQUIRED_SLOTS)

        if missing:
            return {
                "bot_reply": await self._ask_for_slots(missing, lang, context, newly_filled),
                "context": context,
                "results": None,
                "quick_replies": chips_for(missing[0], lang),
                "progress": bar,
            }

        if not context["asked_optional"]:
            context["asked_optional"] = True
            still_want = [f for f in OPTIONAL_SLOTS if context["slots"].get(f) is None]
            if still_want:
                prompt = SLOT_ASK["category_gender"].get(lang, SLOT_ASK["category_gender"][_DEFAULT_LANG])
                # The transition into THIS question is exactly where the last
                # required fact (often estimatedCost or annualIncome — the two
                # that can be silently transformed, e.g. monthly->annual) was
                # just filled. This is a template reply with no LLM call, so
                # the acknowledgment is prepended in code, in English only —
                # good enough for "does this number look right", the real
                # question below is still in the citizen's language.
                if newly_filled:
                    facts = "; ".join(_format_fact(k, v) for k, v in newly_filled.items())
                    prompt = f"Got it — {facts}. {prompt}"
                return {
                    "bot_reply": prompt,
                    "context": context,
                    "results": None,
                    "quick_replies": chips_for("category_gender", lang),
                    "progress": bar,
                }

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
                # No chips on a failure: the only useful action is to retry,
                # and offering next-steps here would imply a verdict exists.
                "quick_replies": [],
                "progress": bar,
            }
        return {
            "bot_reply": _CHECKING.get(lang, _CHECKING[_DEFAULT_LANG]),
            "context": context,
            "results": results,
            # The verdict is on screen — this is the moment the citizen has a
            # decision to make, and the one where a scheme portal normally
            # dead-ends them. Chips here are navigation, not new claims.
            "quick_replies": chips_after_results(lang),
            "progress": bar,
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

    async def _ask_for_slots(
        self, missing: list[str], lang: str, context: dict, newly_filled: dict[str, Any] | None = None,
    ) -> str:
        asks = [SLOT_ASK[f].get(lang, SLOT_ASK[f][_DEFAULT_LANG]) for f in missing[:1]]

        # Without this, a message that stated something OTHER than the still-
        # missing field (e.g. category, before being asked) got the exact same
        # question repeated with no sign it registered — read as a scripted
        # bot ignoring the citizen, which is worse than not asking at all.
        #
        # Facts are formatted HERE, in code, not left for the LLM to restate
        # from a raw number — real bug caught live 2026-09-12: asked to
        # "briefly acknowledge estimatedCost=500", the model invented a "$"
        # sign for what was actually ₹500,00,00,000. Handing it an
        # already-formatted, correctly-scaled string and telling it to quote
        # that exactly removes the one place it was free to guess a currency.
        acknowledge = ""
        if newly_filled:
            facts = "; ".join(_format_fact(k, v) for k, v in newly_filled.items())
            acknowledge = (
                f" The citizen's last message told you: {facts}. Acknowledge that briefly (one short "
                f"clause), quoting those figures EXACTLY as given above — never invent a different "
                f"currency symbol, unit, or number — then ask the question below. Do not just repeat "
                f"a question as if nothing was said."
            )

        prompt = (
            f"You are Sathi, a warm assistant helping a citizen find which concessional credit "
            f"scheme they qualify for.{acknowledge} Ask them this, in 1-2 short sentences: {asks[0]}. "
            f"{language_instruction(lang)}"
        )
        try:
            response = await ainvoke_with_fallback(prompt, temperature=0.3)
            return response.content.strip() or asks[0]
        except Exception:
            return asks[0]
