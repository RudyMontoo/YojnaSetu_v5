"""
Unit coverage for the vision-OCR logic (utils/vision_ocr.py + ocr_router
adapters). Pure functions only — no Ollama, no model, no network — so CI runs
them anywhere. The live model path (image -> structured fields) is
hand-verified per session against real/synthetic documents.
"""
from ai_service.routers.ocr_router import _from_vision, _mask_id
from ai_service.utils.vision_ocr import _correct_doc_type, verhoeff_validate


# ── Aadhaar Verhoeff checksum ──────────────────────────────────────────────────

def test_verhoeff_accepts_valid_aadhaar():
    assert verhoeff_validate("999999990019") is True   # documented UIDAI test number


def test_verhoeff_rejects_random_numbers():
    assert verhoeff_validate("123456789012") is False
    assert verhoeff_validate("000000000000") is False
    assert verhoeff_validate("abcd") is False


# ── doc-type reclassification (fixes small-model misclassification) ────────────

def test_checksum_valid_12digit_is_aadhaar():
    f = {"doc_type": "pan", "id_number": "9999 9999 0019", "raw_text": "आधार"}
    _correct_doc_type(f)
    assert f["doc_type"] == "aadhaar"


def test_pan_pattern_detected():
    f = {"doc_type": "other", "id_number": "ABCDE1234F", "raw_text": ""}
    _correct_doc_type(f)
    assert f["doc_type"] == "pan"


def test_keyword_doc_types():
    for text, expected in [
        ("Income Certificate आय प्रमाण Annual Income", "income_certificate"),
        ("Caste Certificate जाति प्रमाण Scheduled Caste", "caste_certificate"),
        ("Ration Card BPL Below Poverty Line", "ration_card"),
    ]:
        f = {"doc_type": "other", "id_number": None, "raw_text": text}
        _correct_doc_type(f)
        assert f["doc_type"] == expected, text


# ── ID masking (raw ID must never leave the server) ───────────────────────────

def test_mask_aadhaar_shows_only_last4():
    m = _mask_id("9999 9999 0019", "aadhaar")
    assert m == "XXXX-XXXX-0019"
    assert "9999" not in m.replace("0019", "")   # no other digits leak


def test_mask_pan_and_generic():
    assert _mask_id("ABCDE1234F", "pan") == "XXXXX234FX"
    assert _mask_id("1234567", "other").endswith("4567")
    assert _mask_id("12", "other") == "XXXX"     # too short → fully masked


# ── vision fields → response adapter ──────────────────────────────────────────

def test_from_vision_masks_and_flags_bad_checksum():
    label, ids, validity = _from_vision({
        "doc_type": "aadhaar", "id_number": "1234 5678 9012",  # invalid checksum
        "aadhaar_checksum_valid": False, "raw_text": "government of india",
    })
    assert label == "Aadhaar Card"
    assert ids and ids[0].masked_value.startswith("XXXX")
    # a failed Aadhaar checksum must NOT be reported valid
    assert validity["is_valid"] is False
    assert validity["aadhaar_checksum_valid"] is False
