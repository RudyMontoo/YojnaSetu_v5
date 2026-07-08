"""Agent 4's PPO/Aadhaar mismatch core — the Levenshtein ratio and the
date/name normalizers. A regression here silently blocks or approves a
pensioner's DLC, so the threshold behavior is locked down."""
from ai_service.utils.ppo_matcher import (
    MISMATCH_THRESHOLD,
    compute_ppo_mismatch,
    levenshtein,
    normalize_date,
    normalize_name,
)


def test_levenshtein_basics():
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("abc", "") == 3
    assert levenshtein("kitten", "sitting") == 3


def test_normalize_name_collapses_case_and_whitespace():
    assert normalize_name("RAM  KUMAR") == normalize_name("Ram Kumar")
    assert normalize_name("Ram.Kumar!") == "ramkumar"


def test_normalize_date_indian_and_iso_forms_match():
    assert normalize_date("15/08/1952") == normalize_date("1952-08-15") == "1952-08-15"


def test_normalize_date_tolerates_ocr_comma_misread():
    # Real OCR artifact: '15/08/1952' scanned as '15,08/1952'
    assert normalize_date("15,08/1952") == "1952-08-15"


def test_normalize_date_passthrough_on_unknown_format():
    assert normalize_date("August 1952") == "August 1952"


def test_identical_records_are_a_match():
    r = compute_ppo_mismatch("Ram Kumar", "RAM KUMAR", "15/08/1952", "1952-08-15")
    assert r.m_ppo == 0.0
    assert r.name_mismatch is False
    assert r.dob_mismatch is False


def test_clear_name_mismatch_flagged():
    r = compute_ppo_mismatch("Ram Kumar", "Shyam Verma")
    assert r.m_ppo > MISMATCH_THRESHOLD
    assert r.name_mismatch is True


def test_minor_spelling_diff_under_threshold_is_not_mismatch():
    # One-char difference in a long name → ratio well under 0.15
    r = compute_ppo_mismatch("Ramesh Chandra Kumar", "Ramesh Chandra Kumbr")
    assert r.name_mismatch is False


def test_dob_mismatch_detected():
    r = compute_ppo_mismatch("Ram Kumar", "Ram Kumar", "15/08/1952", "16/08/1952")
    assert r.dob_mismatch is True


def test_dob_skipped_when_either_missing():
    r = compute_ppo_mismatch("Ram Kumar", "Ram Kumar", None, "1952-08-15")
    assert r.dob_mismatch is False
    assert r.dob_aadhaar_normalized is None
