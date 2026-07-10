"""
log_redaction.py — the PII-stripping logging middleware CLAUDE.md's security
rules #3 and #8 require: "logging middleware must strip name, phone, Aadhaar-
pattern from all log lines before emission."

pii_masker.py already had the patterns and an `assert_no_pii_in_log` helper,
but nothing was ever installed to actually apply them to emitted logs — so a
stray `logger.info(f"...{raw_phone}...")` anywhere (or in a future edit) would
leak straight into Cloud Run logs. This closes that gap as defense-in-depth:
even though inputs are PII-masked before the LLM and code logs labels not
values, this filter is the safety net that catches anything that slips through.

Design choice: it REDACTS (rule #8's "strip"), it does NOT raise. A logging
filter that threw on PII would crash the very code path trying to log — worse
than the leak. `assert_no_pii_in_log` (raising) stays in pii_masker for tests.
"""
import logging

from ai_service.utils.pii_masker import (
    AADHAAR_PATTERN,
    EID_PATTERN,
    EMAIL_PATTERN,
    PAN_PATTERN,
    PHONE_PATTERN,
)

# EID (28-digit) before AADHAAR (12-digit) so the longer id is consumed first.
_REDACTIONS = [
    (EID_PATTERN, "[EID-REDACTED]"),
    (AADHAAR_PATTERN, "[AADHAAR-REDACTED]"),
    (PAN_PATTERN, "[PAN-REDACTED]"),
    (PHONE_PATTERN, "[PHONE-REDACTED]"),
    (EMAIL_PATTERN, "[EMAIL-REDACTED]"),
]


class PIIRedactionFilter(logging.Filter):
    """Redacts Aadhaar / EID / PAN / phone / email patterns from every log
    record's final message before it is emitted."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()  # interpolates record.args
            redacted = msg
            for pattern, repl in _REDACTIONS:
                redacted = pattern.sub(repl, redacted)
            if redacted != msg:
                record.msg = redacted
                record.args = ()  # message already fully interpolated
        except Exception:  # noqa: BLE001 — logging must NEVER crash the caller
            pass
        return True  # never drop a record; only sanitize it


def install_pii_log_redaction() -> PIIRedactionFilter:
    """Attach the redaction filter to the root logger's handlers, so every
    emitted record (from any module, propagated to root) passes through it.
    Idempotent — safe to call once at startup."""
    f = PIIRedactionFilter()
    root = logging.getLogger()
    root.addFilter(f)  # covers records logged directly on root
    for handler in root.handlers:
        if not any(isinstance(x, PIIRedactionFilter) for x in handler.filters):
            handler.addFilter(f)  # handlers see propagated child records
    return f
