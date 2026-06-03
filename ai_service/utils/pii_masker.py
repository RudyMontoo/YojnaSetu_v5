"""PII Masker — Yojna Setu AI Service

Strips Aadhaar, PAN, phone numbers, and email from any text
before it reaches the LLM. Call this on every user input.

Usage:
    from ai_service.utils.pii_masker import mask_pii, assert_no_pii_in_log

    clean_text, detected = mask_pii(user_input)
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────────
AADHAAR_PATTERN = re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b')
PAN_PATTERN     = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
PHONE_PATTERN   = re.compile(r'\b[6-9]\d{9}\b')
EMAIL_PATTERN   = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')
# Aadhaar enrolment ID (28-digit EID) — sometimes shared instead of UID
EID_PATTERN     = re.compile(r'\b\d{4}[\s/]?\d{5}[\s/]?\d{4}[\s/]?\d{4}[\s/]?\d{4}[\s/]?\d{4}[\s/]?\d{4}\b')


def mask_pii(text: str, user_id: Optional[str] = None) -> tuple[str, list[str]]:
    """
    Masks Aadhaar UID, EID, PAN, phone numbers, and email in text.
    Logs a warning when PII is detected (for audit purposes).

    Args:
        text: Raw input text from user
        user_id: Optional user ID for audit log context

    Returns:
        (masked_text, list_of_detected_pii_types)
    """
    detected = []

    if AADHAAR_PATTERN.search(text):
        text = AADHAAR_PATTERN.sub("[AADHAAR-REDACTED]", text)
        detected.append("aadhaar")

    if EID_PATTERN.search(text):
        text = EID_PATTERN.sub("[EID-REDACTED]", text)
        detected.append("aadhaar_eid")

    if PAN_PATTERN.search(text):
        text = PAN_PATTERN.sub("[PAN-REDACTED]", text)
        detected.append("pan")

    if PHONE_PATTERN.search(text):
        text = PHONE_PATTERN.sub("[PHONE-REDACTED]", text)
        detected.append("phone")

    if EMAIL_PATTERN.search(text):
        text = EMAIL_PATTERN.sub("[EMAIL-REDACTED]", text)
        detected.append("email")

    if detected:
        logger.warning(
            f"[PII_MASKER] Detected and masked: {detected} "
            f"(user={user_id or 'anon'})"
        )

    return text, detected


def assert_no_pii_in_log(log_line: str) -> None:
    """
    Assertion check for logging middleware — raises AssertionError
    if any raw PII pattern is found in a log line before emission.
    Prevents Aadhaar/phone from leaking into Cloud Run logs.

    Usage in logging filter:
        assert_no_pii_in_log(record.getMessage())
    """
    for pattern, label in [
        (AADHAAR_PATTERN, "aadhaar"),
        (PAN_PATTERN, "pan"),
        (PHONE_PATTERN, "phone"),
        (EMAIL_PATTERN, "email"),
    ]:
        if pattern.search(log_line):
            raise AssertionError(
                f"PII LEAK BLOCKED: '{label}' pattern detected in log line. "
                f"Mask before logging. Preview: {log_line[:80]!r}"
            )


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_cases = [
        ("Mera Aadhaar 9876 5432 1234 hai",          ["aadhaar"]),
        ("PAN card ABCDE1234F chahiye",               ["pan"]),
        ("Mere phone pe call karo 9876543210",        ["phone"]),
        ("Email bhejo: ram@gmail.com",                ["email"]),
        ("PM Kisan ke liye apply karna hai",          []),
        ("Aadhaar 1234-5678-9012 aur PAN ABCDE1234F", ["aadhaar", "pan"]),
    ]

    print("PII Masker — Self Test")
    print("=" * 50)
    all_pass = True
    for text, expected in test_cases:
        masked, detected = mask_pii(text)
        ok = set(detected) == set(expected)
        if not ok:
            all_pass = False
        print(f"{'✅' if ok else '❌'} detected={detected} | masked: {masked}")
    print("=" * 50)
    print("ALL TESTS PASSED ✅" if all_pass else "SOME TESTS FAILED ❌")
