"""profile_learner._validated — the whitelist/range gate that stops the
chat-learned-profile feature from writing garbage or a hallucinated field
into a citizen's profile. This is the safety boundary between an LLM's
free-form extraction and a real DB write, so it's tested hard."""
from ai_service.graph.profile_learner import _validated


def test_valid_fields_pass_and_normalize():
    out = _validated({
        "state": "up", "occupation": "Farmer", "category": "OBC",
        "gender": "Male", "annualIncome": 150000, "district": "lucknow",
        "familySize": 5, "landAreaAcres": 2.0, "isBpl": True, "hasLand": True,
    })
    assert out["state"] == "UP"          # upper-cased
    assert out["occupation"] == "farmer"  # lower-cased
    assert out["category"] == "obc"
    assert out["gender"] == "male"
    assert out["district"] == "Lucknow"   # title-cased
    assert out["annualIncome"] == 150000
    assert out["familySize"] == 5
    assert out["landAreaAcres"] == 2.0
    assert out["isBpl"] is True and out["hasLand"] is True


def test_unknown_state_dropped():
    assert "state" not in _validated({"state": "Wakanda"})


def test_invalid_enum_values_dropped():
    out = _validated({"occupation": "astronaut", "category": "royalty", "gender": "robot"})
    assert out == {}


def test_out_of_range_numbers_dropped():
    assert "annualIncome" not in _validated({"annualIncome": -5})
    assert "annualIncome" not in _validated({"annualIncome": 999_999_999})  # > 10 crore cap
    assert "familySize" not in _validated({"familySize": 0})
    assert "familySize" not in _validated({"familySize": 99})
    assert "landAreaAcres" not in _validated({"landAreaAcres": 0})


def test_wrong_types_dropped():
    # LLM might return a string where a number/bool is expected.
    out = _validated({"annualIncome": "one lakh", "isBpl": "yes", "familySize": "5"})
    assert out == {}


def test_unknown_field_never_written():
    # A hallucinated field must not survive — only whitelisted keys pass.
    out = _validated({"aadhaarNumber": "1234", "isVip": True, "state": "MH"})
    assert set(out.keys()) == {"state"}


def test_district_length_bounds():
    assert "district" not in _validated({"district": ""})
    assert "district" not in _validated({"district": "x" * 41})


def test_empty_extraction_returns_empty():
    assert _validated({}) == {}
