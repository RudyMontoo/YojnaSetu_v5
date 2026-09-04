"""
is_first_turn() — real bug fixed 2026-09-04: reply-composing prompts
(eligibility.py, small_talk.py) are single flat strings built only from the
current message, with no chat history — so the LLM had no signal it wasn't
turn one, and kept re-introducing itself ("Namaste! Main Sathi hoon...")
mid-conversation. Confirmed live: a citizen said "Hmm" and "दिखाओ बताओ यही"
well after profile was established and schemes already shown, and got a
full re-introduction both times.
"""
from ai_service.graph.llm import is_first_turn


def test_true_when_only_the_current_message_exists():
    assert is_first_turn([{"role": "user", "content": "hello"}])


def test_true_when_no_messages_at_all():
    assert is_first_turn([])
    assert is_first_turn(None)


def test_false_once_a_prior_exchange_exists():
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "Namaste! Main Sathi hoon..."},
        {"role": "user", "content": "Hmm"},
    ]
    assert not is_first_turn(messages)
