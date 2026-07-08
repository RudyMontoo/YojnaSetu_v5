"""state_match_variants — the fix for the real 2026-07-03 bug where citizen
profiles store 2-char codes ("UP") but schemes store full names ("Uttar
Pradesh"), so a raw-equality query returned only central schemes. A query
built from these variants must match BOTH forms."""
from ai_service.utils.states import state_match_variants


def test_code_expands_to_include_full_name():
    variants = state_match_variants("UP")
    assert "UP" in variants
    assert "Uttar Pradesh" in variants


def test_full_name_expands_to_include_code():
    variants = state_match_variants("Uttar Pradesh")
    assert "Uttar Pradesh" in variants
    assert "UP" in variants


def test_lowercase_code_normalized():
    variants = state_match_variants("up")
    assert "Uttar Pradesh" in variants
    assert "UP" in variants


def test_unknown_state_passes_through_without_crashing():
    # A typo should match nothing, not raise.
    assert state_match_variants("Wakanda") == ["Wakanda"]


def test_empty_returns_empty_list():
    assert state_match_variants("") == []
    assert state_match_variants(None) == []


def test_variants_are_deduped_and_sorted():
    variants = state_match_variants("MH")
    assert variants == sorted(set(variants))
