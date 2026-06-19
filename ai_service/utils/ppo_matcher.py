"""
ppo_matcher.py — PPO/Aadhaar name mismatch detection, per CLAUDE.md's
Agent 4 upgrade spec:

    M_ppo = Levenshtein(N_Aadhaar, N_PPO) / max(len(N_Aadhaar), len(N_PPO))

If M_ppo > 0.15 (more than 15% character difference), flag the mismatch
before DLC submission — this is the single most common reason pension DLC
submissions silently fail (e.g. "Ram Kumar" vs "Ramkumar", or DOB
"15/08/1952" vs "1952-08-15").

Honest discrepancy, not silently smoothed over: CLAUDE.md's own worked
example ("Ram Kumar" vs "Ramkumar") computes to m_ppo = 0.111 under the
formula exactly as specified — BELOW the stated 0.15 threshold, so their own
flagship example wouldn't actually trip their own formula. This module
implements the spec exactly as written (formula + 0.15 threshold) rather
than quietly lowering the threshold to make the anecdote pass; if real
pension-DLC data later shows 0.15 is too high in practice, that's a
threshold-tuning decision to make deliberately, not something to fudge here.

Pure functions, no I/O — deliberately separable from the OCR/LLM extraction
step so the formula itself is directly unit-testable without needing a real
document image or an LLM call.
"""
import re
from dataclasses import dataclass

MISMATCH_THRESHOLD = 0.15


def levenshtein(a: str, b: str) -> int:
    """Classic DP edit distance — no external dependency needed for this."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr_row = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr_row[j] = min(
                curr_row[j - 1] + 1,      # insertion
                prev_row[j] + 1,          # deletion
                prev_row[j - 1] + cost,   # substitution
            )
        prev_row = curr_row
    return prev_row[-1]


def normalize_name(name: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation — so 'Ram Kumar' and
    'RAM  KUMAR' compare as identical, but genuine spelling differences
    ('Ramkumar' vs 'Ram Kumar') still register as edit distance."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


def normalize_date(date_str: str) -> str:
    """Normalizes common Indian document date formats to YYYY-MM-DD so
    '15/08/1952' and '1952-08-15' compare as identical rather than as a
    spurious mismatch. Returns the input unchanged if no known format matches
    — better to compare the raw strings than silently drop the check.

    Also tolerates a comma standing in for '/' — a real OCR misread observed
    when testing Agent 4 against an actual scanned image ('15/08/1952' came
    back as '15,08/1952'). Normalizing that first means noisy OCR output
    doesn't produce a false mismatch on an otherwise-identical date."""
    date_str = date_str.strip().replace(",", "/")
    for sep in ("/", "-", "."):
        parts = date_str.split(sep)
        if len(parts) == 3:
            a, b, c = parts
            if len(a) == 4:  # YYYY-MM-DD already
                return f"{a}-{b.zfill(2)}-{c.zfill(2)}"
            if len(c) == 4:  # DD-MM-YYYY or MM-DD-YYYY — Indian docs are DD-MM-YYYY
                return f"{c}-{b.zfill(2)}-{a.zfill(2)}"
    return date_str


@dataclass
class PpoMismatchResult:
    name_aadhaar_normalized: str
    name_ppo_normalized: str
    m_ppo: float
    name_mismatch: bool
    dob_aadhaar_normalized: str | None
    dob_ppo_normalized: str | None
    dob_mismatch: bool


def compute_ppo_mismatch(
    name_aadhaar: str,
    name_ppo: str,
    dob_aadhaar: str | None = None,
    dob_ppo: str | None = None,
) -> PpoMismatchResult:
    n_aadhaar = normalize_name(name_aadhaar)
    n_ppo = normalize_name(name_ppo)

    distance = levenshtein(n_aadhaar, n_ppo)
    denominator = max(len(n_aadhaar), len(n_ppo), 1)
    m_ppo = round(distance / denominator, 4)

    dob_mismatch = False
    dob_a_norm = dob_p_norm = None
    if dob_aadhaar and dob_ppo:
        dob_a_norm = normalize_date(dob_aadhaar)
        dob_p_norm = normalize_date(dob_ppo)
        dob_mismatch = dob_a_norm != dob_p_norm

    return PpoMismatchResult(
        name_aadhaar_normalized=n_aadhaar,
        name_ppo_normalized=n_ppo,
        m_ppo=m_ppo,
        name_mismatch=m_ppo > MISMATCH_THRESHOLD,
        dob_aadhaar_normalized=dob_a_norm,
        dob_ppo_normalized=dob_p_norm,
        dob_mismatch=dob_mismatch,
    )
