"""
Unit coverage for services/application_assistant.py. Pure-function level for
extraction/detection/payload — no Mongo, no network — plus a handful of
process_message() tests with the products fetcher and LLM call replaced by
fakes, following this suite's existing pattern (status_check.py, etc.) of
never hitting a real LLM/network in a test that runs on every push.
"""
import pytest

from ai_service.services.application_assistant import (
    ApplicationAssistant,
    extract_slots_deterministic,
    is_affirmative,
    is_negative,
)


# ── deterministic slot extraction ───────────────────────────────────────────

def test_extracts_cost_in_lakh_english():
    slots = extract_slots_deterministic("The project cost is 1.5 lakh")
    assert slots["estimatedCost"] == 150_000


def test_extracts_income_in_hinglish():
    slots = extract_slots_deterministic("Meri saalana income 3 lakh hai")
    assert slots["annualIncome"] == 300_000


def test_distinguishes_cost_and_income_in_the_same_message():
    slots = extract_slots_deterministic("Project ki lagat 1 lakh hai, aur income 2.5 lakh")
    assert slots["estimatedCost"] == 100_000
    assert slots["annualIncome"] == 250_000


def test_extracts_category_keyword():
    slots = extract_slots_deterministic("Main SC category se hoon")
    assert slots["category"] == "sc"


def test_extracts_gender_keyword_english_and_hindi():
    assert extract_slots_deterministic("This is for a woman entrepreneur")["gender"] == "female"
    assert extract_slots_deterministic("Yeh ek mahila ke liye hai")["gender"] == "female"


def test_extracts_offline_verification_from_a_branch_visit_english_and_hindi():
    assert extract_slots_deterministic("I'll visit the branch in person")["verificationMode"] == "offline"
    assert extract_slots_deterministic("Main CSC jaakar de dunga")["verificationMode"] == "offline"


def test_extracts_manual_verification_from_a_self_upload_answer():
    assert extract_slots_deterministic("I'll upload them myself")["verificationMode"] == "manual"
    assert extract_slots_deterministic("Main khud scan karke bhej dunga")["verificationMode"] == "manual"


def test_a_branch_visit_wins_over_an_incidental_upload_mention():
    # "they can upload it at the branch" is an OFFLINE answer — the citizen is
    # going in person; someone else does the uploading. Picking manual here
    # would record that this person self-serves online, which they don't.
    slots = extract_slots_deterministic("I'll go to the branch, they can upload it there")
    assert slots["verificationMode"] == "offline"


def test_verification_mode_is_required_so_it_is_never_silently_assumed():
    # The whole point: MANUAL and OFFLINE are both real paths, and defaulting
    # to MANUAL assumes digital access this scheme's applicants may not have.
    from ai_service.services.application_assistant import REQUIRED_SLOTS
    assert "verificationMode" in REQUIRED_SLOTS


def test_never_invents_a_number_when_none_is_stated():
    # "no cost or income mentioned" must not produce a guess — this is the
    # entire point of the deterministic layer existing.
    slots = extract_slots_deterministic("I want to apply for this scheme")
    assert "estimatedCost" not in slots
    assert "annualIncome" not in slots


def test_bare_amount_without_a_unit_is_never_extracted():
    # A bare "5" (no lakh/thousand) is too ambiguous to be a rupee figure —
    # could be a tenure in years, a count of dependents, anything.
    slots = extract_slots_deterministic("mera number 5 hai")
    assert "_bare_amount" not in slots
    assert "estimatedCost" not in slots


# ── affirmative / negative detection ────────────────────────────────────────

@pytest.mark.parametrize("text", ["haan", "yes", "sahi hai", "theek hai", "bilkul", "Yes, correct"])
def test_recognizes_affirmative_english_and_hindi(text):
    assert is_affirmative(text) is True


@pytest.mark.parametrize("text", ["nahi", "no", "galat hai", "wrong"])
def test_recognizes_negative_english_and_hindi(text):
    assert is_negative(text) is True


def test_a_negative_word_is_never_also_read_as_affirmative():
    assert is_affirmative("nahi, galat hai") is False


# ── payload shape ────────────────────────────────────────────────────────────

def _confirmed_context():
    return {
        "scheme_code": "micro-finance",
        "slots": {
            "_scheme_name": "Micro Finance Scheme (MFS)",
            "estimatedCost": 120_000,
            "annualIncome": 250_000,
            "category": "sc",
        },
        "missing_required": [],
        "awaiting_confirmation": True,
        "confirmed": False,
    }


def test_payload_matches_spring_create_body_shape_exactly():
    payload = ApplicationAssistant.build_payload(_confirmed_context())
    assert set(payload) == {
        "schemeCode", "productId", "estimatedCost", "annualIncome",
        "category", "tenureMonths", "moratoriumMode", "verificationMode",
    }
    assert payload["productId"] == "micro-finance"
    assert payload["estimatedCost"] == 120_000
    assert payload["annualIncome"] == 250_000
    assert payload["verificationMode"] == "manual"


def test_payload_carries_the_offline_choice_through():
    context = _confirmed_context()
    context["slots"]["verificationMode"] = "offline"
    assert ApplicationAssistant.build_payload(context)["verificationMode"] == "offline"


def test_payload_defaults_category_to_sc_when_unstated():
    context = _confirmed_context()
    context["slots"].pop("category")
    payload = ApplicationAssistant.build_payload(context)
    assert payload["category"] == "sc"


# ── process_message, with the network boundary faked ───────────────────────

class _FakeProducts:
    async def __call__(self):
        return [{"id": "micro-finance", "name": "Micro Finance Scheme (MFS)"}]


@pytest.mark.asyncio
async def test_asks_which_scheme_when_none_is_named_or_pinned():
    assistant = ApplicationAssistant(products_fetcher=_FakeProducts())
    result = await assistant.process_message("I want to apply for a loan", "en", {})
    assert result["structured_payload"] is None
    assert result["context"]["scheme_code"] is None


@pytest.mark.asyncio
async def test_resolves_pinned_scheme_from_a_pronoun_reference():
    assistant = ApplicationAssistant(products_fetcher=_FakeProducts())
    context = {"_last_shown_scheme_code": "micro-finance"}
    result = await assistant.process_message("I want to apply for this scheme", "en", context)
    assert result["context"]["scheme_code"] == "micro-finance"


@pytest.mark.asyncio
async def test_confirmation_yields_structured_payload_only_after_yes(monkeypatch):
    # LLM slot extraction isn't exercised here — both required slots are
    # already filled deterministically, so _extract_slots_llm never runs.
    assistant = ApplicationAssistant(products_fetcher=_FakeProducts())
    context = {
        "scheme_code": "micro-finance",
        "slots": {"_scheme_name": "MFS", "estimatedCost": 100_000, "annualIncome": 200_000, "category": "sc"},
        "missing_required": [],
        "awaiting_confirmation": True,
        "confirmed": False,
    }
    result = await assistant.process_message("haan sahi hai", "hi", context)
    assert result["structured_payload"] is not None
    assert result["structured_payload"]["productId"] == "micro-finance"
    assert result["context"]["confirmed"] is True
