"""
application_assistant.py — goal-directed slot-filling for SC credit
applications.

Collects exactly the fields CreditApplicationController.create() needs
(Spring gateway), in the citizen's selected language, then hands back a
payload shaped for that exact endpoint — never more, never invented.

Numbers are NEVER guessed. Two extraction layers, in order:
  1. extract_slots_deterministic() — pure regex over explicit rupee/lakh
     mentions and category/gender keywords. No LLM, no ambiguity, fully
     unit-testable without a network call (same "pure function first" split
     status_check.py and eligibility_rules_engine.py already use in this
     codebase).
  2. _extract_slots_llm() — LLM JSON extraction for anything layer 1 didn't
     catch (mixed-language phrasing, indirect statements). Prompted to
     return null for anything not explicitly stated — never to estimate.
Layer 1's result always wins over layer 2 for the same key: a citizen who
says a precise number should never have it silently overridden by an LLM's
looser read of the same sentence.

Scheme/product data (name, id) comes from Spring's real catalogue via
utils/spring_client.fetch_credit_products() — never invented, never a
second source of truth alongside CreditProductSeeder.

verificationMode is ASKED, not defaulted. VerificationMode.java has two
available paths — MANUAL (citizen uploads scans) and OFFLINE (documents
presented in person at a branch/CSC) — and quietly picking MANUAL for
everyone would assume a level of digital access and literacy that a large
share of this scheme's applicants don't have. DIGILOCKER and
ACCOUNT_AGGREGATOR are deliberately not offered here: they're gated off
server-side (isAvailable() == false), so proposing them conversationally
would promise a route create() will reject.
"""
import logging
import re
from typing import Any

from ai_service.graph.llm import ainvoke_with_fallback, language_instruction
from ai_service.utils.spring_client import fetch_credit_products

logger = logging.getLogger(__name__)

REQUIRED_SLOTS = ["estimatedCost", "annualIncome", "verificationMode"]
OPTIONAL_SLOTS = ["category", "gender", "tenureMonths", "moratoriumMode"]

SLOT_ASK: dict[str, dict[str, str]] = {
    "estimatedCost": {
        "en": "What's the total project cost you're estimating?",
        "hi": "Aapke project ki total lagat kitni hogi (andazan)?",
    },
    "annualIncome": {
        "en": "What's your annual family income?",
        "hi": "Aapki saalana family income kitni hai?",
    },
    # Required, not optional — MANUAL (upload yourself) and OFFLINE (in
    # person at a branch/CSC) are both real, equally supported paths
    # (VerificationMode.java). Defaulting silently to one would quietly
    # assume every citizen can self-upload scans, which is exactly the
    # digital-literacy gap this module exists to not create.
    "verificationMode": {
        "en": "Will you upload your documents yourself, or would you rather visit a branch or CSC in person?",
        "hi": "Kya aap khud documents upload karenge, ya branch/CSC jaakar in-person jama karna chahenge?",
    },
    "category": {
        "en": "Just to confirm — are you applying under the SC category?",
        "hi": "Confirm karna tha — aap SC category ke under apply kar rahe hain?",
    },
    "gender": {
        "en": "Is this application for a woman entrepreneur? There's a lower-rate scheme for that.",
        "hi": "Kya yeh application ek mahila udyami ke liye hai? Uske liye kam byaj wali scheme hai.",
    },
}

PRIVACY_LINE = {
    "en": "This stays within your application — I'm only asking what the form itself needs.",
    "hi": "Yeh sirf aapke application ke liye hai — main sirf wahi puch raha hoon jo form mein chahiye.",
}

_ASK_FALLBACK = {
    "en": "I need a couple more details: {asks} {privacy}",
    "hi": "Mujhe kuch aur details chahiye: {asks} {privacy}",
}
_CONFIRM_FALLBACK = {
    "en": "Confirmed! I've prepared your application — continue below to review and submit it.",
    "hi": "Confirm ho gaya! Maine aapka application taiyaar kar diya hai — neeche review karke submit karein.",
}
_WHICH_SCHEME = {
    "en": "Which scheme would you like to apply for?",
    "hi": "Aap kaunsi scheme ke liye apply karna chahte hain?",
}
_DEFAULT_LANG = "en"


# ── deterministic extraction (layer 1) ──────────────────────────────────────

# "1.5 lakh", "1,20,000", "50000", "₹2 lakh" — Indian-style amount phrasing.
_AMOUNT_RE = re.compile(
    r"(?:rs\.?|₹|inr)?\s*([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|lakhs|thousand|k)?",
    re.IGNORECASE,
)
_INCOME_KEYWORDS = re.compile(
    r"income|saalana|salana|aay|kamai|earning|salary|vetan", re.IGNORECASE
)
_COST_KEYWORDS = re.compile(
    r"cost|lagat|kharcha|kharch|project|budget|kimat|price", re.IGNORECASE
)
_CATEGORY_MAP = {
    "sc": re.compile(r"\bsc\b|scheduled caste|anusuchit jaati", re.IGNORECASE),
    "st": re.compile(r"\bst\b|scheduled tribe|anusuchit janjaati", re.IGNORECASE),
    "obc": re.compile(r"\bobc\b|other backward", re.IGNORECASE),
    "general": re.compile(r"\bgeneral\b|general category", re.IGNORECASE),
}
_GENDER_MAP = {
    "female": re.compile(r"\bwoman\b|\bwomen\b|female|mahila|महिला", re.IGNORECASE),
    "male": re.compile(r"\bman\b|\bmen\b|\bmale\b|purush", re.IGNORECASE),
}
# Checked offline-first: "branch"/"CSC"/"in person" is a specific, deliberate
# statement, while "upload" can appear incidentally in either answer ("I'll
# visit the branch, they can upload it there"). Only VerificationMode's two
# AVAILABLE modes are detectable here — digilocker/account_aggregator are
# gated off server-side (VerificationMode.isAvailable()), so offering them
# conversationally would promise a path create() will reject.
_VERIFICATION_MODE_MAP = {
    "offline": re.compile(
        r"\bbranch\b|\bcsc\b|in[-\s]?person|walk[-\s]?in|jaakar|jaunga|jaaunga|jayenge|visit",
        re.IGNORECASE,
    ),
    "manual": re.compile(
        r"\bupload\b|\bscan\b|khud|myself|online|photo\s*bhej|send\s*photo",
        re.IGNORECASE,
    ),
}
_AFFIRMATIVE_RE = re.compile(
    r"\b(haan|ha|han|yes|yeah|yep|sahi|correct|theek|thik|ok|okay|sure|bilkul)\b", re.IGNORECASE
)
_NEGATIVE_RE = re.compile(
    r"\b(nahi|nahin|no|nope|galat|wrong|incorrect)\b", re.IGNORECASE
)


def _to_number(raw: str, unit: str | None) -> float:
    n = float(raw.replace(",", ""))
    unit = (unit or "").lower()
    if unit in ("lakh", "lac", "lakhs"):
        return n * 100_000
    if unit == "thousand" or unit == "k":
        return n * 1_000
    return n


def extract_slots_deterministic(text: str) -> dict[str, Any]:
    """Regex-only extraction — no LLM, no guessing. Returns only keys it is
    confident about; callers merge this over the LLM layer, never the other
    way round. A message with two numbers ("cost 1 lakh, income 3 lakh")
    assigns each number to whichever keyword sentence-fragment it's nearer,
    so it doesn't need both keywords present to work for a single amount."""
    if not text:
        return {}

    slots: dict[str, Any] = {}

    for keyword_re, key in ((_COST_KEYWORDS, "estimatedCost"), (_INCOME_KEYWORDS, "annualIncome")):
        for m in keyword_re.finditer(text):
            # search the amount nearest AFTER the keyword within ~40 chars —
            # "income 3 lakh, cost 1 lakh" must not cross-assign.
            window = text[m.end(): m.end() + 40]
            amount_m = _AMOUNT_RE.search(window)
            if amount_m and amount_m.group(1):
                slots[key] = _to_number(amount_m.group(1), amount_m.group(2))
                break

    # Single bare amount, no keyword at all (e.g. just "1.5 lakh") — only
    # useful when exactly one slot is still open; ambiguous otherwise, so we
    # deliberately leave it for the caller/LLM layer rather than guess which.
    if "estimatedCost" not in slots and "annualIncome" not in slots:
        amount_m = _AMOUNT_RE.search(text)
        if amount_m and amount_m.group(1) and amount_m.group(2):  # require a unit — a bare "5" is too ambiguous
            slots["_bare_amount"] = _to_number(amount_m.group(1), amount_m.group(2))

    for value, pattern in _CATEGORY_MAP.items():
        if pattern.search(text):
            slots["category"] = value
            break

    for value, pattern in _GENDER_MAP.items():
        if pattern.search(text):
            slots["gender"] = value
            break

    for value, pattern in _VERIFICATION_MODE_MAP.items():
        if pattern.search(text):
            slots["verificationMode"] = value
            break

    return slots


def is_affirmative(text: str) -> bool:
    return bool(_AFFIRMATIVE_RE.search(text or "")) and not _NEGATIVE_RE.search(text or "")


def is_negative(text: str) -> bool:
    return bool(_NEGATIVE_RE.search(text or ""))


# ── the assistant ────────────────────────────────────────────────────────────

class ApplicationAssistant:
    def __init__(self, products_fetcher=fetch_credit_products):
        # Injectable for tests — real caller uses the default (Spring HTTP call).
        self._fetch_products = products_fetcher

    async def process_message(
        self, user_text: str, language: str, context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Args:
            user_text: the citizen's message, this turn.
            language: UI-selected code ('en'|'hi'|'bn'|'ta'|'te'|'mr').
            context: {scheme_code, slots, missing_required, awaiting_confirmation,
                      confirmed} — see docs/APPLICATION_ASSISTANT.md. Empty dict
                      on a fresh conversation.

        Returns:
            {"bot_reply": str, "context": dict, "structured_payload": dict | None}
        """
        context = self._normalize(context)
        lang = (language or "").strip().lower()

        if not context["scheme_code"]:
            scheme = await self._resolve_scheme(user_text, context)
            if not scheme:
                return {
                    "bot_reply": _WHICH_SCHEME.get(lang, _WHICH_SCHEME[_DEFAULT_LANG]),
                    "context": context,
                    "structured_payload": None,
                }
            context["scheme_code"] = scheme["id"]
            context["slots"]["_scheme_name"] = scheme.get("name", "")

        if context.get("awaiting_confirmation"):
            if is_affirmative(user_text) and not is_negative(user_text):
                context["confirmed"] = True
                payload = self.build_payload(context)
                return {
                    "bot_reply": _CONFIRM_FALLBACK.get(lang, _CONFIRM_FALLBACK[_DEFAULT_LANG]),
                    "context": context,
                    "structured_payload": payload,
                }
            # Not a plain "yes" — could be a correction ("nahi, income 4 lakh hai").
            # Fall through: merge whatever new facts this message states, then
            # re-summarize instead of silently re-asking the same question.
            context["awaiting_confirmation"] = False

        await self._merge_slots(user_text, context)

        missing = [f for f in REQUIRED_SLOTS if context["slots"].get(f) is None]
        context["missing_required"] = missing

        if missing:
            context["awaiting_confirmation"] = False
            return {
                "bot_reply": await self._ask_for_slots(missing, lang, context),
                "context": context,
                "structured_payload": None,
            }

        context["awaiting_confirmation"] = True
        return {
            "bot_reply": await self._compose_summary(context, lang),
            "context": context,
            "structured_payload": None,
        }

    @staticmethod
    def _normalize(context: dict[str, Any]) -> dict[str, Any]:
        context = dict(context or {})
        context.setdefault("scheme_code", None)
        context["slots"] = dict(context.get("slots") or {})
        context.setdefault("missing_required", list(REQUIRED_SLOTS))
        context.setdefault("awaiting_confirmation", False)
        context.setdefault("confirmed", False)
        return context

    # ── scheme resolution ────────────────────────────────────────────────

    # Strips a trailing "(MFS)"-style code off a product name before matching —
    # CreditProductSeeder names every scheme "Full Name (CODE)", and requiring
    # the code to also appear verbatim in the citizen's message (an exact
    # substring match did exactly that, and never matched anything as a real
    # bug caught live 2026-09-11: "Micro Finance Scheme" alone never matched
    # "Micro Finance Scheme (MFS)") is not something a citizen would ever say.
    _NAME_CODE_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")

    @classmethod
    def _significant_words(cls, name: str) -> set[str]:
        stripped = cls._NAME_CODE_SUFFIX.sub("", name or "")
        return {w for w in stripped.lower().split() if len(w) > 2}

    def _match_by_name(self, user_text: str, products: list[dict]) -> dict | None:
        """Word-overlap match, not substring — the same fix
        graph/agents/application_guidance.py's _best_name_match already made
        for the general scheme catalogue, applied here for the same reason:
        a citizen names the scheme they mean, close enough to be recognized
        by a human, not necessarily character-for-character."""
        text_words = self._significant_words(user_text)
        if not text_words:
            return None

        best, best_overlap = None, 0
        for product in products:
            name_words = self._significant_words(product.get("name", ""))
            if not name_words:
                continue
            overlap = len(text_words & name_words)
            if overlap > best_overlap:
                best, best_overlap = product, overlap

        # A short name ("KCC") needs less overlap to count as named than a
        # long one ("Aajeevika Micro-Finance Yojana") — the bar is "most of
        # the name's real words showed up", not a fixed count.
        if best is None:
            return None
        required = min(2, len(self._significant_words(best.get("name", ""))))
        return best if best_overlap >= max(required, 1) else None

    async def _resolve_scheme(self, user_text: str, context: dict) -> dict | None:
        """"Is scheme ke liye" (this scheme) only resolves against a scheme
        already pinned earlier this conversation (context["_last_shown_scheme_code"],
        set by the caller from the session's schemesShown) — never guessed
        from a bare pronoun with nothing to anchor it to."""
        products = await self._fetch_products()
        if not products:
            return None

        pinned = context.get("_last_shown_scheme_code")
        if pinned and re.search(r"\b(is|this|isi|ye|yeh|isme)\b", user_text or "", re.IGNORECASE):
            return next((p for p in products if p.get("id") == pinned), None)

        by_id = next((p for p in products if p.get("id", "") and p["id"] in (user_text or "").lower()), None)
        if by_id:
            return by_id

        return self._match_by_name(user_text, products)

    # ── slot extraction ──────────────────────────────────────────────────
    async def _merge_slots(self, user_text: str, context: dict) -> None:
        deterministic = extract_slots_deterministic(user_text)
        bare_amount = deterministic.pop("_bare_amount", None)

        # A bare amount only fills a slot if exactly one required slot is
        # still open — resolves "cost 1 lakh" ... "3 lakh" as a follow-up
        # answer to whichever question was just asked, without guessing when
        # both are still open.
        still_missing = [f for f in REQUIRED_SLOTS if context["slots"].get(f) is None]
        if bare_amount is not None and len(still_missing) == 1:
            deterministic[still_missing[0]] = bare_amount

        for key, value in deterministic.items():
            context["slots"][key] = value

        # LLM layer only for whatever layer 1 still hasn't filled — never
        # overrides a deterministic hit for the same key.
        still_open = [f for f in (REQUIRED_SLOTS + OPTIONAL_SLOTS) if context["slots"].get(f) is None]
        if still_open:
            llm_extracted = await self._extract_slots_llm(user_text)
            for key in still_open:
                if llm_extracted.get(key) is not None:
                    context["slots"][key] = llm_extracted[key]

    async def _extract_slots_llm(self, user_text: str) -> dict[str, Any]:
        prompt = f"""Extract ONLY facts explicitly stated in this message. Do NOT infer, estimate, \
or round any number that wasn't actually said — if it's not clearly stated, return null for it.

Message: "{user_text}"

Return ONLY a JSON object with these keys (use null for anything not stated):
{{"estimatedCost": <number in rupees or null>, "annualIncome": <number in rupees or null>, \
"category": "<sc|st|obc|general or null>", "gender": "<male|female or null>", \
"tenureMonths": <number or null>, "moratoriumMode": "<capitalise|service_interest or null>", \
"verificationMode": "<manual if they'll upload documents themselves, offline if they'll go to a branch/CSC in person, or null>"}}"""
        try:
            response = await ainvoke_with_fallback(prompt, temperature=0.0, tags=["internal"])
            return self._safe_json(response.content)
        except Exception as e:
            logger.warning("Application assistant slot extraction failed: %s", e)
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

    # ── reply composition ────────────────────────────────────────────────
    async def _ask_for_slots(self, missing: list[str], lang: str, context: dict) -> str:
        asks = [SLOT_ASK[f].get(lang, SLOT_ASK[f][_DEFAULT_LANG]) for f in missing[:2]]
        privacy = PRIVACY_LINE.get(lang, PRIVACY_LINE[_DEFAULT_LANG])
        scheme_name = context["slots"].get("_scheme_name", "")
        prompt = f"""You are the SC Credit Application Assistant, helping fill in an application for \
"{scheme_name}". Ask the citizen these questions, warmly, in 2-3 sentences total: {' / '.join(asks)}. \
Also include, once, this reassurance: "{privacy}". {language_instruction(lang)}"""
        try:
            response = await ainvoke_with_fallback(prompt, temperature=0.3)
            return response.content.strip() or self._ask_fallback(asks, privacy, lang)
        except Exception:
            return self._ask_fallback(asks, privacy, lang)

    @staticmethod
    def _ask_fallback(asks: list[str], privacy: str, lang: str) -> str:
        template = _ASK_FALLBACK.get(lang, _ASK_FALLBACK[_DEFAULT_LANG])
        return template.format(asks=" ".join(asks), privacy=privacy)

    async def _compose_summary(self, context: dict, lang: str) -> str:
        s = context["slots"]
        scheme_name = s.get("_scheme_name", "")
        verification = {
            "manual": "you'll upload your documents yourself",
            "offline": "you'll take your documents to a branch or CSC in person",
        }.get(s.get("verificationMode"), "")
        facts = (
            f"Scheme: {scheme_name}; Project cost: Rs {s.get('estimatedCost')}; "
            f"Annual income: Rs {s.get('annualIncome')}; Category: {s.get('category', 'SC')}"
            + (f"; Verification: {verification}" if verification else "")
        )
        prompt = f"""Summarize these application facts back to the citizen for confirmation, ending with \
a clear yes/no question ("Is this correct?"). Facts: {facts}. {language_instruction(lang)} \
Keep it to 2-3 sentences, plain numbers (no invented details)."""
        try:
            response = await ainvoke_with_fallback(prompt, temperature=0.1)
            return response.content.strip() or self._summary_fallback(facts, lang)
        except Exception:
            return self._summary_fallback(facts, lang)

    @staticmethod
    def _summary_fallback(facts: str, lang: str) -> str:
        question = {"en": "Is this correct?", "hi": "Kya yeh sahi hai?"}.get(lang, "Is this correct?")
        return f"{facts}. {question}"

    # ── payload — shaped EXACTLY like CreditApplicationController.create()'s body ──
    @staticmethod
    def build_payload(context: dict) -> dict:
        s = context["slots"]
        return {
            "schemeCode": context["scheme_code"],   # for the frontend route /apply/:schemeId
            "productId": context["scheme_code"],    # exact key CreditApplicationController.create() expects
            "estimatedCost": s["estimatedCost"],
            "annualIncome": s["annualIncome"],
            "category": s.get("category") or "sc",
            "tenureMonths": s.get("tenureMonths"),        # None is fine — form pre-fills the scheme default
            "moratoriumMode": s.get("moratoriumMode"),    # None is fine, same reason
            # Asked, never assumed: "manual" (citizen uploads scans) and
            # "offline" (in person at a branch/CSC) are both live paths in
            # VerificationMode.java, and silently picking manual would assume
            # a level of digital access many applicants don't have. The
            # fallback only fires if a caller built a context that skipped
            # the question entirely.
            "verificationMode": s.get("verificationMode") or "manual",
        }
