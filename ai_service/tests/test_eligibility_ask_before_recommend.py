"""
compute_systemic_gaps() — the "ask before recommend" decision logic
(eligibility.py). Pure function, no Mongo/LLM — same contract as the rest
of ai_service/tests/.

What's pinned here: a field missing for a MAJORITY of the top candidates
triggers a clarifying question (the profile is genuinely too thin for this
query); a field missing for only a minority does NOT (that's one scheme's
own idiosyncratic requirement, already handled as a one-off mention rather
than blocking the whole reply on it).
"""
from collections import Counter

from ai_service.graph.agents.eligibility import compute_systemic_gaps


def test_no_candidates_means_no_gaps():
    assert compute_systemic_gaps(Counter(), 0) == []


def test_field_missing_for_all_candidates_is_systemic():
    # "give me pension scheme" against an empty profile — every candidate
    # is missing annualIncome and dob alike.
    counts = Counter({"annualIncome": 5, "dob": 5})
    assert compute_systemic_gaps(counts, 5) == ["annualIncome", "dob"]


def test_field_missing_for_minority_is_not_systemic():
    # only 1 of 5 candidates happens to need "hasLand" — a one-off ask, not
    # a sign the whole query is under-specified.
    counts = Counter({"hasLand": 1})
    assert compute_systemic_gaps(counts, 5) == []


def test_exact_majority_boundary():
    # 5 candidates, ceil(5/2) = 3 — exactly 3 missing counts as systemic, 2 does not.
    assert compute_systemic_gaps(Counter({"state": 3}), 5) == ["state"]
    assert compute_systemic_gaps(Counter({"state": 2}), 5) == []


def test_single_candidate_majority_is_one():
    # ceil(1/2) = 1 — even a single top candidate missing one field is
    # "systemic" for that (thin) result set.
    assert compute_systemic_gaps(Counter({"category": 1}), 1) == ["category"]


def test_ranked_most_missing_first():
    counts = Counter({"annualIncome": 4, "dob": 5, "state": 3})
    assert compute_systemic_gaps(counts, 5) == ["dob", "annualIncome", "state"]


def test_never_returns_a_field_not_in_the_input_counter():
    # sanity: this function never invents a field name — it only ever
    # ranks/filters whatever evaluate_eligibility already flagged.
    counts = Counter({"isBpl": 3})
    result = compute_systemic_gaps(counts, 5)
    assert set(result) <= set(counts)
