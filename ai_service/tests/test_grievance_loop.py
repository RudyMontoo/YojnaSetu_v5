"""
Unit coverage for Agent 5's grievance-loop guard clauses
(graph/agents/grievance.py: attach_cpgrams_reference).

The full Mongo path (record -> list -> attach ref -> ownership isolation) is
hand-verified end-to-end per session. What's pinned here is the input
validation that must short-circuit BEFORE any DB access — so these run with
db=None and prove no query is attempted on bad input (a DB call on None would
raise AttributeError, which the test would surface).
"""
import asyncio

from ai_service.graph.agents.grievance import attach_cpgrams_reference


def test_bad_objectid_returns_none_without_db():
    # invalid ObjectId must be rejected before touching the db (db=None proves it)
    assert asyncio.run(attach_cpgrams_reference(None, "citizen", "not-an-objectid", "REF/1")) is None


def test_empty_ref_returns_none_without_db():
    # a syntactically-valid id but empty/whitespace ref must short-circuit too
    valid_id = "0123456789abcdef01234567"  # 24-hex, parses as ObjectId
    assert asyncio.run(attach_cpgrams_reference(None, "citizen", valid_id, "")) is None
    assert asyncio.run(attach_cpgrams_reference(None, "citizen", valid_id, "   ")) is None
