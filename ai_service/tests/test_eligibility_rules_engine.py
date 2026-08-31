"""
Unit coverage for eligibility_rules_engine.py (Problem 4 redesign). Pure
function, no Mongo/LLM — same contract as the rest of ai_service/tests/.

What's pinned here: the engine must never fabricate a criterion the scheme
doesn't specify, never guess when the citizen's profile is missing a field
the scheme DOES specify, and must correctly distinguish "not eligible"
(a real failed criterion) from "insufficient data" (nothing failed, but
something couldn't be checked).
"""
from ai_service.graph.agents.eligibility_rules_engine import evaluate_eligibility


def test_eligible_when_all_specified_criteria_match():
    profile = {"annualIncome": 100000, "dob": "1990-01-01", "category": "obc",
               "occupation": "farmer", "isBpl": True, "isRural": True, "hasLand": True, "state": "UP"}
    scheme = {
        "state": "Uttar Pradesh",
        "eligibilityRules": {
            "maxIncome": 200000, "minAge": 18, "maxAge": 60,
            "category": ["obc", "sc", "st"], "occupation": ["farmer"],
            "isBpl": True, "isRural": True, "hasLand": True,
        },
    }
    result = evaluate_eligibility(profile, scheme)
    assert result["verdict"] == "eligible"
    assert not result["failed"]
    assert not result["missing_profile_data"]


def test_not_eligible_when_income_exceeds_cap():
    profile = {"annualIncome": 500000}
    scheme = {"eligibilityRules": {"maxIncome": 200000}}
    result = evaluate_eligibility(profile, scheme)
    assert result["verdict"] == "not_eligible"
    assert any("exceeds" in f for f in result["failed"])


def test_insufficient_data_when_profile_missing_required_field():
    # scheme specifies a category requirement; citizen profile has none
    profile = {}
    scheme = {"eligibilityRules": {"category": ["sc", "st"]}}
    result = evaluate_eligibility(profile, scheme)
    assert result["verdict"] == "insufficient_data"
    assert "category" in result["missing_profile_data"]
    assert not result["failed"]  # never guessed a failure


def test_missing_criteria_not_confused_with_missing_profile_data():
    # scheme has NO income rule at all — this must be "missing_criteria",
    # not "missing_profile_data", even though the citizen also has no income on file
    profile = {}
    scheme = {"eligibilityRules": {}}
    result = evaluate_eligibility(profile, scheme)
    assert "income" in result["missing_criteria"]
    assert "annualIncome" not in result["missing_profile_data"]
    assert result["rules_are_empty"] is True


def test_age_computed_from_dob_correctly():
    from datetime import date
    this_year = date.today().year
    profile = {"dob": f"{this_year - 70}-01-01"}  # clearly 70+, avoids leap-year edge cases
    scheme = {"eligibilityRules": {"minAge": 60}}
    result = evaluate_eligibility(profile, scheme)
    assert result["verdict"] == "eligible"
    assert any("age 70" in m for m in result["matched"])


def test_unparseable_dob_is_missing_profile_data_not_a_crash():
    profile = {"dob": "not-a-date"}
    scheme = {"eligibilityRules": {"minAge": 18}}
    result = evaluate_eligibility(profile, scheme)
    assert result["verdict"] == "insufficient_data"
    assert "dob" in result["missing_profile_data"]


def test_state_specific_scheme_fails_for_wrong_state():
    profile = {"state": "MH"}
    scheme = {"state": "Uttar Pradesh", "eligibilityRules": {}}
    result = evaluate_eligibility(profile, scheme)
    assert result["verdict"] == "not_eligible"
    assert any("state-specific" in f for f in result["failed"])


def test_central_scheme_has_no_state_requirement():
    profile = {"state": "MH"}
    scheme = {"state": None, "eligibilityRules": {}}
    result = evaluate_eligibility(profile, scheme)
    assert not any("state" in f for f in result["failed"])


def test_never_fabricates_bpl_requirement_when_scheme_does_not_ask():
    profile = {"isBpl": False}
    scheme = {"eligibilityRules": {"isBpl": False}}  # explicit non-True -> treated as "not required"
    result = evaluate_eligibility(profile, scheme)
    assert "BPL status" in result["missing_criteria"]
    assert not result["failed"]
