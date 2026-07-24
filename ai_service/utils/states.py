"""
states.py — Indian state/UT code ↔ name mapping.

Why this exists (real bug, found 2026-07-03 by Agent 10's state-gaps
metric): citizen_profiles.state stores 2-char codes ("UP", per CLAUDE.md's
schema), but schemes.state stores full names ("Uttar Pradesh" — what
MyScheme's API and the migration JSONs actually contain). The eligibility
vector search filtered schemes by the profile's raw code, matching nothing
— every citizen silently got ONLY central schemes, never their own state's.
`state_match_variants()` lets queries match either representation.
"""

STATE_CODE_TO_NAME = {
    "AN": "Andaman & Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh (UT)",
    "CG": "Chhattisgarh",
    "DN": "Dadra, Daman & Diu",
    "DL": "Delhi",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JK": "Jammu & Kashmir",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh (UT)",
    "LD": "Lakshadweep",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PY": "Puducherry",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "WB": "West Bengal",
}

_NAME_TO_CODE = {name.lower(): code for code, name in STATE_CODE_TO_NAME.items()}


def parse_state_district(text: str) -> tuple[str | None, str | None]:
    """Best-effort (state_code, district) from a free-text address — a small
    vision model reliably writes the full address but often leaves the separate
    state/district fields null, so we recover them here. Longest state name
    first so 'West Bengal' wins over a stray 'Bengal'. District = the segment
    just before the state mention (fuzzy, but good enough to prefill)."""
    if not text:
        return None, None
    low = text.lower()
    state_name = next((n for n in sorted(STATE_CODE_TO_NAME.values(), key=len, reverse=True)
                       if n.lower() in low), None)
    if not state_name:
        return None, None
    code = _NAME_TO_CODE[state_name.lower()]
    before = text[:low.rfind(state_name.lower())].rstrip(" ,-–")
    district = before.split(",")[-1].strip() if "," in before else None
    return code, (district or None)


def state_match_variants(state: str) -> list[str]:
    """Given either a 2-char code or a full name, returns every string form
    that should be treated as the same state in a Mongo match. Unknown
    inputs pass through as a single-element list rather than erroring —
    a typo'd state should just match nothing, not crash a search."""
    if not state:
        return []
    s = state.strip()
    variants = {s}
    if s.upper() in STATE_CODE_TO_NAME:
        variants.add(s.upper())
        variants.add(STATE_CODE_TO_NAME[s.upper()])
    if s.lower() in _NAME_TO_CODE:
        variants.add(_NAME_TO_CODE[s.lower()])
    return sorted(variants)
