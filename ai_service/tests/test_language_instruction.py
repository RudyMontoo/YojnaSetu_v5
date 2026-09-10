"""
Unit coverage for graph/llm.py's language_instruction() — the fix for a real
bug: every reply-composing agent used to infer the reply's language purely
from the citizen's message text/script, silently discarding state["lang"]
(the language the citizen explicitly selected in the UI). Confirmed live as
the "bot replies in the wrong language" report. Pure-function level — no
LLM, no network.
"""
from ai_service.graph.llm import LANGUAGE_NAMES, language_instruction


def test_known_code_names_the_language_explicitly():
    instruction = language_instruction("ta")
    assert "Tamil" in instruction
    assert "ONLY" in instruction


def test_every_frontend_language_switcher_code_is_covered():
    # Must mirror frontend/src/lib/i18n.jsx's LANGUAGES exactly — a code the
    # switcher offers but this dict doesn't know falls through to the
    # message-inference fallback, silently breaking the UI toggle for that
    # language only.
    assert set(LANGUAGE_NAMES) == {"en", "hi", "bn", "ta", "te", "mr"}


def test_case_and_whitespace_insensitive():
    assert language_instruction(" Bn ") == language_instruction("bn")


def test_unknown_or_missing_code_falls_back_to_message_inference():
    for bad in (None, "", "fr", "xx"):
        instruction = language_instruction(bad)
        assert "SAME language" in instruction
        assert "ONLY" not in instruction


def test_fallback_never_silently_claims_a_specific_language():
    # The fallback path must not name any language — it's a script-inference
    # instruction, not a language selection.
    for name in LANGUAGE_NAMES.values():
        assert name not in language_instruction("unknown-code")
