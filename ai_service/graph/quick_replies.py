"""
quick_replies.py — the tappable answer chips Sathi offers alongside each
question it asks.

Why this exists: the eligibility conversation was correct but inert. A citizen
landed on a blank text box and a generic "ask me anything", which is the exact
failure of every government scheme portal — the person who doesn't know the
vocabulary has nothing to type, so they leave. Every question this flow asks
has a small, known answer space (business vs education; a social category; a
rough cost bracket), so the answer can be a tap instead of a sentence. That
turns a 5-message typing chore on a phone keyboard into four taps.

The chips are not a separate input path: each one carries the literal SENTENCE
it sends, phrased so that eligibility_assistant.extract_slots_deterministic()
picks it up with its existing regexes (the amount chips deliberately include
"cost"/"income" so _COST_KEYWORDS/_INCOME_KEYWORDS match, rather than relying
on the bare-amount fallback, which only fires when exactly one of the two is
still missing). So a tap and a typed answer go down the same path, and nothing
here can produce a figure — it only produces what the citizen said.

Amounts are brackets, not a claim: they are common starting points to save
typing, and the citizen can always type an exact number instead. They are
input, never output — no chip ever states a loan amount, rate, or verdict.

Language follows SLOT_ASK's existing convention: en + hi, falling back to en.
"""
from typing import Any

_DEFAULT_LANG = "en"

# Keyed by the slot being asked. Each chip is {label, value}: `label` is what
# the citizen sees on the chip, `value` is the message actually sent — kept
# separate so the visible chip can stay short while the sent sentence carries
# the keyword the extractor needs.
CHIPS: dict[str, dict[str, list[dict[str, str]]]] = {
    "need": {
        "en": [
            {"label": "🏪 A business or shop", "value": "It's for a business I want to start"},
            {"label": "🎓 Education or a course", "value": "It's for education — a course and fees"},
        ],
        "hi": [
            {"label": "🏪 Business ya dukaan", "value": "Yeh business ke liye hai"},
            {"label": "🎓 Padhai ya course", "value": "Yeh education ke liye hai — course aur fees"},
        ],
    },
    "estimatedCost": {
        "en": [
            {"label": "≈ ₹50,000", "value": "The total cost is about ₹50,000"},
            {"label": "≈ ₹2 lakh", "value": "The total cost is about ₹2 lakh"},
            {"label": "≈ ₹5 lakh", "value": "The total cost is about ₹5 lakh"},
            {"label": "≈ ₹10 lakh", "value": "The total cost is about ₹10 lakh"},
        ],
        "hi": [
            {"label": "≈ ₹50,000", "value": "Total kharcha lagbhag ₹50,000 hai"},
            {"label": "≈ ₹2 lakh", "value": "Total kharcha lagbhag ₹2 lakh hai"},
            {"label": "≈ ₹5 lakh", "value": "Total kharcha lagbhag ₹5 lakh hai"},
            {"label": "≈ ₹10 lakh", "value": "Total kharcha lagbhag ₹10 lakh hai"},
        ],
    },
    "annualIncome": {
        "en": [
            {"label": "Under ₹1 lakh / year", "value": "Our family income is about ₹80,000 a year"},
            {"label": "≈ ₹1.5 lakh / year", "value": "Our family income is about ₹1.5 lakh a year"},
            {"label": "≈ ₹3 lakh / year", "value": "Our family income is about ₹3 lakh a year"},
            {"label": "Over ₹5 lakh / year", "value": "Our family income is about ₹6 lakh a year"},
        ],
        "hi": [
            {"label": "₹1 lakh se kam", "value": "Parivar ki saalana income lagbhag ₹80,000 hai"},
            {"label": "≈ ₹1.5 lakh saal", "value": "Parivar ki saalana income lagbhag ₹1.5 lakh hai"},
            {"label": "≈ ₹3 lakh saal", "value": "Parivar ki saalana income lagbhag ₹3 lakh hai"},
            {"label": "₹5 lakh se zyada", "value": "Parivar ki saalana income lagbhag ₹6 lakh hai"},
        ],
    },
    # Asked as one combined question (SLOT_ASK["category_gender"]), so the
    # chips answer both at once. "Skip" is a real option, not a dead end:
    # asked_optional is already set by the time these are shown, so the next
    # turn runs the real eligibility check either way — the API's own
    # missingProfileData/insufficient_data states cover what wasn't said.
    "category_gender": {
        "en": [
            {"label": "SC — for a woman", "value": "I am SC and this is for a woman"},
            {"label": "SC — for a man", "value": "I am SC and this is for a man"},
            {"label": "OBC", "value": "I am OBC"},
            {"label": "Skip this", "value": "I'd rather not say — please carry on"},
        ],
        "hi": [
            {"label": "SC — mahila ke liye", "value": "Main SC hoon aur yeh mahila ke liye hai"},
            {"label": "SC — purush ke liye", "value": "Main SC hoon aur yeh purush ke liye hai"},
            {"label": "OBC", "value": "Main OBC hoon"},
            {"label": "Chhod dein", "value": "Yeh nahi batana chahta — aage badhiye"},
        ],
    },
}

# Shown once the real eligibility verdict is on screen. Without these the
# conversation dead-ends at exactly the moment the citizen has a decision to
# make — which is where a scheme portal normally loses them.
AFTER_RESULTS: dict[str, list[dict[str, str]]] = {
    "en": [
        {"label": "What documents do I need?", "value": "What documents will I need for this?"},
        {"label": "Where do I apply?", "value": "Where is the nearest branch or CSC I can apply at?"},
        {"label": "What will the EMI be?", "value": "What would the monthly repayment look like?"},
        {"label": "Start my application", "value": "I want to apply for this scheme"},
    ],
    "hi": [
        {"label": "Kaunse documents chahiye?", "value": "Iske liye kaunse documents lagenge?"},
        {"label": "Apply kahan karein?", "value": "Sabse nazdeeki branch ya CSC kahan hai?"},
        {"label": "EMI kitni hogi?", "value": "Har mahine kitna wapas karna hoga?"},
        {"label": "Application shuru karein", "value": "Main is scheme ke liye apply karna chahta hoon"},
    ],
}


def chips_for(slot: str, lang: str) -> list[dict[str, str]]:
    """Chips for the slot currently being asked. Unknown slot -> no chips,
    which degrades to the plain text box rather than to a wrong suggestion."""
    by_lang = CHIPS.get(slot)
    if not by_lang:
        return []
    return by_lang.get((lang or "").strip().lower(), by_lang[_DEFAULT_LANG])


def chips_after_results(lang: str) -> list[dict[str, str]]:
    return AFTER_RESULTS.get((lang or "").strip().lower(), AFTER_RESULTS[_DEFAULT_LANG])


def progress(slots: dict[str, Any], required: list[str]) -> dict[str, int]:
    """`{answered, total}` for the "question 2 of 3" hint under the chips.

    A conversation with no visible end is one a citizen abandons — they can't
    tell if it's three questions or thirty. Counts only the REQUIRED slots:
    the optional category/gender round is asked once and never blocks, so
    including it would make the bar stall at "almost done" and then jump.
    """
    answered = sum(1 for f in required if slots.get(f) is not None)
    return {"answered": answered, "total": len(required)}
