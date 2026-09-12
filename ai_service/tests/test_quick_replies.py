"""
The chips in graph/quick_replies.py are only useful if the sentence each one
sends survives eligibility_assistant's DETERMINISTIC extractor. If a chip's
wording drifts out of the regexes' reach, nothing breaks loudly — the tap just
falls through to the LLM extractor, or to the same question being asked again,
and the citizen sees a bot that ignored their tap. That's the exact failure the
chips were added to remove, so it's locked down here.

Deterministic extraction also means a tapped conversation needs zero LLM calls
for slot-filling, which is what lets the flow complete when the provider quota
is exhausted — worth keeping true.
"""
import pytest

from ai_service.graph.quick_replies import (
    AFTER_RESULTS, CHIPS, chips_after_results, chips_for, progress,
)
from ai_service.services.eligibility_assistant import (
    REQUIRED_SLOTS, extract_slots_deterministic,
)

_SKIP_LABELS = {"Skip this", "Chhod dein"}


@pytest.mark.parametrize(
    ("slot", "lang", "chip"),
    [
        (slot, lang, chip)
        for slot, by_lang in CHIPS.items()
        for lang, chips in by_lang.items()
        for chip in chips
    ],
)
def test_chip_value_extracts_the_slot_it_answers(slot, lang, chip):
    extracted = extract_slots_deterministic(chip["value"])
    extracted.pop("_bare_amount", None)

    if chip["label"] in _SKIP_LABELS:
        assert extracted == {}, "a skip chip must not assert any fact about the citizen"
        return

    if slot == "category_gender":
        # This one question fills two slots; a chip must fill at least category.
        assert extracted.get("category") is not None
    else:
        assert extracted.get(slot) is not None, (
            f"chip {chip['label']!r} sends {chip['value']!r}, which the deterministic "
            f"extractor does not read as {slot}"
        )


def test_chips_never_assert_a_fact_they_were_not_asked_for():
    """A cost chip that also set annualIncome (or vice versa) would silently
    answer a question the citizen was never shown — the extractor's keyword
    windows make this easy to get wrong when rewording a chip."""
    for slot in ("estimatedCost", "annualIncome"):
        other = "annualIncome" if slot == "estimatedCost" else "estimatedCost"
        for chips in CHIPS[slot].values():
            for chip in chips:
                assert extract_slots_deterministic(chip["value"]).get(other) is None


def test_every_slot_offers_chips_in_every_supported_language():
    langs = {lang for by_lang in CHIPS.values() for lang in by_lang}
    for slot, by_lang in CHIPS.items():
        assert set(by_lang) == langs, f"{slot} is missing a language"
    assert set(AFTER_RESULTS) == langs


def test_unknown_slot_and_language_degrade_to_no_wrong_suggestion():
    assert chips_for("nonexistent_slot", "en") == []
    # An unsupported language falls back to English chips rather than to none —
    # the citizen can still tap, and the reply prose is already localised.
    assert chips_for("need", "ta") == CHIPS["need"]["en"]
    assert chips_after_results("ta") == AFTER_RESULTS["en"]


def test_progress_counts_only_answered_required_slots():
    assert progress({}, REQUIRED_SLOTS) == {"answered": 0, "total": 3}
    assert progress({"need": "business"}, REQUIRED_SLOTS) == {"answered": 1, "total": 3}
    # An explicit None is "not answered yet", not an answer — the assistant
    # stores slots that way before they're filled.
    assert progress({"need": None, "estimatedCost": 50000}, REQUIRED_SLOTS)["answered"] == 1
    # Optional slots must not inflate the bar, or it stalls near the end.
    assert progress(
        {"need": "business", "estimatedCost": 1, "annualIncome": 1, "category": "sc"},
        REQUIRED_SLOTS,
    ) == {"answered": 3, "total": 3}


@pytest.mark.asyncio
async def test_tap_only_conversation_completes_with_every_llm_call_failing(monkeypatch):
    """The whole point of chips on demo day: a citizen who only taps never
    needs the LLM for slot-filling, so the flow still reaches a real verdict
    when the provider quota is exhausted and every fallback is down.

    Asserted as a hard requirement, not a nice-to-have — if a future chip stops
    extracting deterministically, this is the test that catches it before a
    judge does.
    """
    import ai_service.services.eligibility_assistant as ea

    async def dead_llm(*args, **kwargs):
        raise RuntimeError("all providers exhausted")

    called = {}

    async def fake_check(payload):
        called["payload"] = payload
        return {"verdict": "eligible", "recommendations": [{"code": "MFS", "name": "Micro Finance"}]}

    monkeypatch.setattr(ea, "ainvoke_with_fallback", dead_llm)
    monkeypatch.setattr(ea, "check_credit_eligibility", fake_check)

    assistant = ea.EligibilityAssistant()
    context: dict = {}
    message = "I want to start a small shop of my own"

    for _ in range(len(REQUIRED_SLOTS) + 2):   # + the optional round, + the check
        turn = await assistant.process_message(message, "en", context)
        context = turn["context"]
        if turn["results"]:
            break
        assert turn["quick_replies"], "a question with no chips leaves a tap-only citizen stuck"
        message = turn["quick_replies"][0]["value"]
    else:
        pytest.fail("tap-only conversation never reached a verdict")

    assert turn["results"]["verdict"] == "eligible"
    assert called["payload"]["need"] == "business"
    assert called["payload"]["category"] == "sc"
    # Post-verdict chips are navigation to the next step, never a new claim.
    assert turn["quick_replies"] == AFTER_RESULTS["en"]
