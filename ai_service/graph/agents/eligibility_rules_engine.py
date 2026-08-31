"""
eligibility_rules_engine.py — real, criteria-by-criteria eligibility
comparison for Agent 1 (Problem 4 redesign).

Replaces the old `score_eligibility` keyword-in-free-text heuristic (which
never even read a scheme's structured `eligibilityRules`, only fuzzy-matched
words in its description) with an honest comparison: a scheme's actual
`eligibilityRules` JSON (produced by discovery/normalizer.py's extraction —
`{maxIncome, minAge, maxAge, category, occupation, isRural, isBpl, hasLand}`)
against the citizen's actual profile fields (annualIncome, category,
occupation, isBpl, isDisabled, isRural, hasLand, dob, state — the real
Spring Boot CitizenProfile field names).

Three distinct "I don't know" cases, kept separate on purpose so a reply can
be honest about which one applies (ground rule: never fabricate a criterion
that isn't there, and never silently guess when profile data is missing):
  - the scheme has no rule for a criterion at all (nothing to check)
  - the scheme has a rule but the citizen's profile lacks the field needed
  - the scheme's eligibilityRules is empty/near-empty entirely (discovery
    hasn't extracted usable criteria for this scheme yet)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ai_service.utils.states import state_match_variants

_DOB_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")


def _age_from_dob(dob: str | None) -> int | None:
    if not dob:
        return None
    for fmt in _DOB_FORMATS:
        try:
            born = datetime.strptime(dob.strip(), fmt).date()
            today = date.today()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except ValueError:
            continue
    return None


def evaluate_eligibility(profile: dict[str, Any], scheme: dict[str, Any]) -> dict[str, Any]:
    """Returns {verdict, matched, failed, missing_criteria, missing_profile_data}.

    verdict is one of: "eligible", "not_eligible", "insufficient_data".
    "insufficient_data" means: nothing failed outright, but at least one
    criterion the scheme DOES specify couldn't be checked because the
    citizen's profile is missing that field — this is Path B's trigger to
    ask for exactly those fields (or offer Lens/CSC), not a guess either way.
    """
    rules = scheme.get("eligibilityRules") or {}
    matched: list[str] = []
    failed: list[str] = []
    missing_criteria: list[str] = []
    missing_profile_data: list[str] = []

    # -- income --
    max_income = rules.get("maxIncome")
    if max_income is None:
        missing_criteria.append("income")
    else:
        income = profile.get("annualIncome")
        if income is None:
            missing_profile_data.append("annualIncome")
        elif income <= max_income:
            matched.append(f"annual income ₹{income} is within the ₹{max_income} limit")
        else:
            failed.append(f"annual income ₹{income} exceeds the ₹{max_income} limit")

    # -- age --
    min_age, max_age = rules.get("minAge"), rules.get("maxAge")
    if min_age is None and max_age is None:
        missing_criteria.append("age")
    else:
        age = _age_from_dob(profile.get("dob"))
        if age is None:
            missing_profile_data.append("dob")
        else:
            age_ok = (min_age is None or age >= min_age) and (max_age is None or age <= max_age)
            desc = f"age {age}" + (f" (needs {min_age or '0'}-{max_age or '∞'})" if not age_ok else "")
            (matched if age_ok else failed).append(desc)

    # -- category (general/obc/sc/st) --
    category_list = rules.get("category") or []
    if not category_list:
        missing_criteria.append("category")
    else:
        citizen_category = (profile.get("category") or "").lower() or None
        if citizen_category is None:
            missing_profile_data.append("category")
        elif citizen_category in [c.lower() for c in category_list]:
            matched.append(f"category '{citizen_category}' matches")
        else:
            failed.append(f"category '{citizen_category}' not in required {category_list}")

    # -- occupation --
    occupation_list = rules.get("occupation") or []
    if not occupation_list:
        missing_criteria.append("occupation")
    else:
        citizen_occupation = (profile.get("occupation") or "").lower() or None
        if citizen_occupation is None:
            missing_profile_data.append("occupation")
        elif citizen_occupation in [o.lower() for o in occupation_list]:
            matched.append(f"occupation '{citizen_occupation}' matches")
        else:
            failed.append(f"occupation '{citizen_occupation}' not in required {occupation_list}")

    # -- isBpl --
    requires_bpl = rules.get("isBpl")
    if requires_bpl is not True:
        missing_criteria.append("BPL status")
    else:
        is_bpl = profile.get("isBpl")
        if is_bpl is None:
            missing_profile_data.append("isBpl")
        elif is_bpl:
            matched.append("BPL status confirmed")
        else:
            failed.append("scheme requires BPL status, citizen is not marked BPL")

    # -- isRural --
    requires_rural = rules.get("isRural")
    if requires_rural is None:
        missing_criteria.append("rural/urban")
    else:
        is_rural = profile.get("isRural")
        if is_rural is None:
            missing_profile_data.append("isRural")
        elif is_rural == requires_rural:
            matched.append("rural/urban status matches")
        else:
            failed.append(f"scheme requires isRural={requires_rural}, citizen is {is_rural}")

    # -- hasLand --
    requires_land = rules.get("hasLand")
    if requires_land is None:
        missing_criteria.append("land ownership")
    else:
        has_land = profile.get("hasLand")
        if has_land is None:
            missing_profile_data.append("hasLand")
        elif has_land == requires_land:
            matched.append("land-ownership requirement matches")
        else:
            failed.append(f"scheme requires hasLand={requires_land}, citizen is {has_land}")

    # -- state (top-level scheme field, not in eligibilityRules; None = central scheme, open to all states) --
    scheme_state = scheme.get("state")
    if scheme_state is not None:
        citizen_state = profile.get("state")
        if not citizen_state:
            missing_profile_data.append("state")
        elif scheme_state in state_match_variants(citizen_state):
            matched.append(f"state '{scheme_state}' matches")
        else:
            failed.append(f"scheme is state-specific to '{scheme_state}', citizen is elsewhere")

    if failed:
        verdict = "not_eligible"
    elif missing_profile_data:
        verdict = "insufficient_data"
    else:
        verdict = "eligible"

    return {
        "verdict": verdict,
        "matched": matched,
        "failed": failed,
        "missing_criteria": missing_criteria,
        "missing_profile_data": missing_profile_data,
        "rules_are_empty": not rules,
    }
