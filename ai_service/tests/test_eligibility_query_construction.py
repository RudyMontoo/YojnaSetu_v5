"""
build_retrieval_query() / detect_show_everything() — the fix for a real,
severe bug (2026-09-03): the old query construction discarded the citizen's
actual message entirely whenever their profile had ANY field set, because
`build_query_string(profile) or last_user_message or "..."` short-circuits
on the first non-empty string. A citizen with occupation=student asking
about a dairy farm loan was searched as if they'd typed "student <state>".

What's pinned here: the real message is ALWAYS present in the query now,
regardless of profile content; profile terms are additive, never a
replacement; and an explicit "show me everything" request drops profile
bias entirely.
"""
from ai_service.graph.agents.eligibility import build_retrieval_query, detect_show_everything, find_topic_anchor


def test_real_message_never_discarded_when_profile_has_data():
    # the exact bug scenario: profile has occupation set, citizen asks
    # something entirely unrelated to that occupation
    profile = {"occupation": "student", "state": "UP"}
    query = build_retrieval_query("dairy farm loan schemes", profile, show_everything=False)
    assert "dairy farm loan schemes" in query


def test_substantive_message_is_not_diluted_by_profile_terms():
    # real bug fixed 2026-09-04, caught live: profile occupation=student,
    # citizen asked (in Hindi) about PENSION schemes — blending "student UP"
    # into the same short embedded query pulled retrieval toward education
    # content instead. A message with real topical content (>=4 words) must
    # search on its own; profile terms would only dilute it.
    profile = {"occupation": "student", "state": "UP"}
    query = build_retrieval_query("मुझे पेंशन स्कीम्स के बारे में जानना है", profile, show_everything=False)
    assert "student" not in query
    assert "मुझे पेंशन स्कीम्स के बारे में जानना है" in query


def test_thin_message_still_gets_profile_assist():
    # a vague/short message has no topic of its own — profile terms are
    # genuinely useful here, unlike the substantive-message case above
    profile = {"occupation": "farmer", "state": "UP"}
    query = build_retrieval_query("koi scheme dikhao", profile, show_everything=False)
    assert "koi scheme dikhao" in query
    assert "farmer" in query


def test_empty_message_falls_back_to_profile_only():
    profile = {"occupation": "farmer"}
    query = build_retrieval_query("", profile, show_everything=False)
    assert "farmer" in query


def test_empty_message_and_empty_profile_falls_back_to_generic():
    query = build_retrieval_query("", {}, show_everything=False)
    assert query == "government welfare scheme"


def test_show_everything_drops_profile_hint_entirely():
    profile = {"occupation": "student", "state": "UP", "category": "obc"}
    query = build_retrieval_query("show me everything", profile, show_everything=True)
    assert "student" not in query
    assert "OBC" not in query
    assert "show me everything" in query


def test_detect_show_everything_matches_common_phrasings():
    assert detect_show_everything("show me everything please")
    assert detect_show_everything("sab schemes dikhao")
    assert detect_show_everything("I want to see all scheme options")


def test_detect_show_everything_false_for_normal_queries():
    assert not detect_show_everything("dairy farm loan schemes")
    assert not detect_show_everything("hello")
    assert not detect_show_everything("")


def test_detect_show_everything_handles_none():
    assert not detect_show_everything(None)


def test_find_topic_anchor_recovers_prior_real_message():
    # the exact reported bug: "show me everything" as the current message
    # has no topic of its own, and the immediate prior message is just a
    # thin clarifying-question answer ("UP") — must skip that and recover
    # the real "dairy farm business" topic from further back
    messages = [
        {"role": "user", "content": "I want a loan to start a dairy farm business"},
        {"role": "assistant", "content": "Sure, tell me your state..."},
        {"role": "user", "content": "UP"},
        {"role": "assistant", "content": "Here are a couple of matches..."},
        {"role": "user", "content": "show me everything"},
    ]
    assert find_topic_anchor(messages) == "I want a loan to start a dairy farm business"


def test_find_topic_anchor_skips_earlier_override_phrases_too():
    messages = [
        {"role": "user", "content": "dairy farm loan schemes"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "sab schemes dikhao"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "show me everything"},
    ]
    assert find_topic_anchor(messages) == "dairy farm loan schemes"


def test_find_topic_anchor_empty_when_no_prior_message():
    assert find_topic_anchor([{"role": "user", "content": "show me everything"}]) == ""


def test_find_topic_anchor_ignores_non_user_roles():
    messages = [
        {"role": "assistant", "content": "some prior reply"},
        {"role": "user", "content": "show me everything"},
    ]
    assert find_topic_anchor(messages) == ""
