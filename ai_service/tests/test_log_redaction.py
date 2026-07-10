"""
Regression coverage for the PII-stripping log filter (utils/log_redaction.py),
CLAUDE.md security rules #3/#8. Self-contained — no network, no Mongo.

This is the defense-in-depth net: even if some future log line interpolates a
raw Aadhaar/phone, it must be redacted before emission.
"""
import logging

from ai_service.utils.log_redaction import PIIRedactionFilter


def _redact(msg, *args):
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)
    PIIRedactionFilter().filter(rec)
    return rec.getMessage()


def test_aadhaar_redacted():
    out = _redact("uid 9876 5432 1234 here")
    assert "9876 5432 1234" not in out and "AADHAAR-REDACTED" in out


def test_phone_redacted():
    out = _redact("call 9876543210 now")
    assert "9876543210" not in out and "PHONE-REDACTED" in out


def test_email_and_pan_redacted():
    out = _redact("mail ram@gmail.com pan ABCDE1234F")
    assert "ram@gmail.com" not in out and "ABCDE1234F" not in out


def test_redacts_through_log_args():
    # PII arriving via %-args (the common logger.info("x %s", val) shape)
    out = _redact("phone is %s", "9876543210")
    assert "9876543210" not in out and "PHONE-REDACTED" in out


def test_non_pii_untouched():
    out = _redact("PM Kisan scheme for farmers in UP")
    assert out == "PM Kisan scheme for farmers in UP"


def test_filter_never_drops_record():
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "any", (), None)
    assert PIIRedactionFilter().filter(rec) is True
