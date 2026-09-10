"""
credit_faq.py — pure-function coverage for match_products()/_format_product_facts(),
plus an agent-level test with a mocked db/LLM. This is the credit module's own
RAG: retrieval by keyword/code match against `credit_products` (no embedding
field, small exact catalogue), never vector search — see the module docstring
for why. What's pinned here: a real code (e.g. "MFS") outranks generic word
overlap, an unmatched question falls back to an honest "which scheme?" reply
listing real product names (never a silent guess), and an unverified
product's figures always get flagged rather than stated as settled fact.
"""
from unittest.mock import AsyncMock, patch

import pytest

from ai_service.graph.agents.credit_faq import (
    _format_product_facts,
    match_products,
    run_credit_faq_agent,
)

MFS = {
    "id": "micro-finance", "code": "MFS", "name": "Micro Finance Scheme",
    "type": "micro", "projectType": "small",
    "unitCostFloor": None, "unitCostCeiling": 140000, "maxLoanAmount": 125000,
    "interestRate": 6.5, "moratoriumMonths": 3, "maxTenureMonths": 36,
    "coveragePct": 90, "maxAnnualIncome": 500000, "categories": ["sc"],
    "womenOnly": False, "channelPartnerTypes": ["SCA", "PSB"],
    "figuresVerified": True, "active": True,
}
TERM_LOAN = {
    "id": "term-loan", "code": "TL", "name": "Term Loan",
    "type": "term", "projectType": "large",
    "unitCostFloor": 140001, "unitCostCeiling": 5000000, "maxLoanAmount": 4500000,
    "interestRate": 8.0, "moratoriumMonths": 6, "maxTenureMonths": 84,
    "coveragePct": 90, "maxAnnualIncome": 500000, "categories": ["sc"],
    "womenOnly": False, "channelPartnerTypes": ["SCA", "PSB"],
    "figuresVerified": True, "active": True,
}
MSY = {
    "id": "mahila-samriddhi", "code": "MSY", "name": "Mahila Samriddhi Yojana",
    "type": "micro", "projectType": "small",
    "unitCostFloor": None, "unitCostCeiling": 140000, "maxLoanAmount": 125000,
    "interestRate": 4.0, "moratoriumMonths": 3, "maxTenureMonths": 36,
    "coveragePct": 90, "maxAnnualIncome": 500000, "categories": ["sc"],
    "womenOnly": True, "channelPartnerTypes": ["COOPERATIVE", "NBFC_MFI"],
    "figuresVerified": False, "active": True,
}
CATALOGUE = [MFS, TERM_LOAN, MSY]


# ----------------------------------------------------------------- matching

def test_exact_code_match_wins_over_word_overlap():
    matched = match_products("TL ka interest rate kya hai", CATALOGUE)
    assert matched[0]["code"] == "TL"


def test_scheme_name_words_match_the_right_product():
    matched = match_products("micro finance scheme mein kitna loan milega", CATALOGUE)
    assert matched[0]["code"] == "MFS"


def test_no_overlap_returns_no_matches():
    assert match_products("aaj mausam kaisa hai", CATALOGUE) == []


def test_empty_query_returns_no_matches():
    assert match_products("", CATALOGUE) == []
    assert match_products(None, CATALOGUE) == []


def test_generic_credit_question_can_match_multiple_products():
    # "loan" and "scheme" are generic overlap words shared by every product —
    # top_k caps the result rather than returning every unrelated candidate.
    matched = match_products("loan scheme details batao", CATALOGUE, top_k=2)
    assert len(matched) <= 2


def test_a_strong_code_match_excludes_a_weak_trailing_match():
    # Real case from live testing: "Term Loan ka interest rate" scored Term
    # Loan correctly on top via its code, but also weakly matched Micro
    # Finance on the single shared word "loan" — handing the LLM a second,
    # unrelated scheme's numbers for a single-scheme question is worse than
    # not matching it at all.
    matched = match_products("TL interest rate kitna hai", CATALOGUE)
    assert [p["code"] for p in matched] == ["TL"]


# ------------------------------------------------------------- fact format

def test_facts_include_the_real_numbers_not_a_placeholder():
    facts = _format_product_facts(MFS)
    assert "6.5" in facts
    assert "125,000" in facts
    assert "90%" in facts
    assert "3 months" in facts


def test_unverified_product_is_flagged():
    facts = _format_product_facts(MSY)
    assert "provisional" in facts.lower() or "not independently verified" in facts.lower()


def test_verified_product_carries_no_warning():
    facts = _format_product_facts(MFS)
    assert "provisional" not in facts.lower()


def test_women_only_is_surfaced():
    assert "women applicants only" in _format_product_facts(MSY)


# --------------------------------------------------------------- the agent

class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length):
        return self._docs


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, query):
        return _FakeCursor(self._docs)


class _FakeDb:
    def __init__(self, docs):
        self._docs = docs

    def __getitem__(self, name):
        assert name == "credit_products"
        return _FakeCollection(self._docs)


@pytest.mark.asyncio
async def test_agent_grounds_reply_in_the_matched_product_only():
    db = _FakeDb(CATALOGUE)
    state = {"messages": [{"role": "user", "content": "TL ka interest rate kya hai"}], "lang": "en"}

    fake_response = AsyncMock()
    fake_response.content = "The Term Loan carries 8.0% interest."
    with patch("ai_service.graph.agents.credit_faq.ainvoke_with_fallback", return_value=fake_response):
        result = await run_credit_faq_agent(state, db)

    assert result["active_schemes"][0]["code"] == "TL"
    assert result["reply"] == "The Term Loan carries 8.0% interest."
    assert result["agent_outputs"]["credit_faq"]["matched_codes"] == ["TL"]


@pytest.mark.asyncio
async def test_agent_gives_an_honest_no_match_reply_listing_real_schemes():
    db = _FakeDb(CATALOGUE)
    state = {"messages": [{"role": "user", "content": "aaj mausam kaisa hai"}], "lang": "en"}

    result = await run_credit_faq_agent(state, db)

    assert result["active_schemes"] == []
    assert "Micro Finance Scheme" in result["reply"]
    assert "Term Loan" in result["reply"]


@pytest.mark.asyncio
async def test_agent_falls_back_honestly_when_the_llm_call_fails():
    db = _FakeDb(CATALOGUE)
    state = {"messages": [{"role": "user", "content": "MFS ka interest rate?"}], "lang": "en"}

    with patch("ai_service.graph.agents.credit_faq.ainvoke_with_fallback", side_effect=RuntimeError("down")):
        result = await run_credit_faq_agent(state, db)

    assert "Micro Finance Scheme" in result["reply"]
    assert result["active_schemes"][0]["code"] == "MFS"
