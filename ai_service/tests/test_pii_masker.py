"""Security rule #8 (CLAUDE.md): PII must be stripped before any text reaches
the LLM. These lock down the masking patterns so a future edit can't silently
let an Aadhaar/PAN/phone/email through."""
from ai_service.utils.pii_masker import mask_pii


def test_masks_aadhaar_with_and_without_separators():
    for raw in ("my aadhaar is 1234 5678 9012", "1234-5678-9012", "123456789012"):
        masked, detected = mask_pii(raw)
        assert "aadhaar" in detected
        assert "1234" not in masked and "9012" not in masked
        assert "[AADHAAR-REDACTED]" in masked


def test_masks_pan():
    masked, detected = mask_pii("PAN: ABCDE1234F please")
    assert "pan" in detected
    assert "ABCDE1234F" not in masked


def test_masks_indian_mobile_number():
    masked, detected = mask_pii("call me on 9876543210")
    assert "phone" in detected
    assert "9876543210" not in masked


def test_does_not_flag_non_mobile_number():
    # PHONE_PATTERN requires a leading 6-9 and exactly 10 digits — a random
    # 10-digit id starting with 1 shouldn't be masked as a phone.
    _, detected = mask_pii("order number 1234509876")
    assert "phone" not in detected


def test_masks_email():
    masked, detected = mask_pii("reach me at rajesh.kumar@example.co.in")
    assert "email" in detected
    assert "@example" not in masked


def test_masks_multiple_pii_in_one_message():
    masked, detected = mask_pii("Aadhaar 1234 5678 9012, PAN ABCDE1234F, ph 9876543210")
    assert {"aadhaar", "pan", "phone"} <= set(detected)


def test_clean_text_passes_through_unchanged():
    text = "I am a farmer in Uttar Pradesh looking for crop insurance schemes"
    masked, detected = mask_pii(text)
    assert masked == text
    assert detected == []


def test_empty_input_is_safe():
    assert mask_pii("") == ("", [])
